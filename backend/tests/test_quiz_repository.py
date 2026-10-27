from __future__ import annotations

import pytest

from app.core.db import Database
from app.repositories.quiz_repository import QuizRepository
from app.repositories.user_repository import UserRepository
from app.services.xp_rules import XP_PER_COMPLETION, XP_PER_CORRECT, calculate_xp

pytestmark = pytest.mark.integration

QUESTIONS = [
    {
        "id": "q1",
        "type": "single",
        "stem": "题干一",
        "options": [{"key": "A", "text": "选项 A"}, {"key": "B", "text": "选项 B"}],
        "answer": ["A"],
        "explanation": "解析一",
        "knowledge_point": "概念",
        "difficulty": "easy",
    }
]
RECORDS = [
    {"question_id": "q1", "selected_answers": ["A"], "is_correct": True, "duration_ms": 1200},
]
REPORT = {
    "accuracy": 100,
    "total": 1,
    "correct": 1,
    "mastered_points": ["概念"],
    "weak_points": [],
    "three_line_summary": ["一", "二", "三"],
    "advice": ["建议"],
    "share_quote": "金句",
}


async def create_user(database: Database) -> int:
    repo = UserRepository(database)
    user = await repo.create(openid="openid-persist-test")
    return user.id


def test_xp_rule_matches_documentation() -> None:
    assert XP_PER_COMPLETION == 10
    assert XP_PER_CORRECT == 2
    assert calculate_xp(correct_count=4) == 18
    assert calculate_xp(correct_count=0) == 10


async def test_save_quiz_is_idempotent(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)

    await repo.save_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        title="RAG 入门",
        summary="摘要",
        user_input="RAG",
        questions=QUESTIONS,
    )
    await repo.save_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        title="RAG 入门（覆盖）",
        summary="摘要",
        user_input="RAG",
        questions=QUESTIONS,
    )

    quiz = await repo.get_quiz("quiz_1")
    assert quiz is not None
    assert quiz["title"] == "RAG 入门（覆盖）"
    assert len(quiz["questions"]) == 1


async def test_save_quiz_returns_none_for_unknown_id(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)

    assert await repo.get_quiz("quiz_missing") is None


async def test_complete_quiz_persists_all_tables_and_awards_xp(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_repo = UserRepository(mysql_db)
    user_id = await create_user(mysql_db)

    awarded = await repo.complete_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=calculate_xp(1),
    )

    assert awarded is True
    assert (await repo.get_answer_records("quiz_1")) == RECORDS
    assert (await repo.get_report("quiz_1"))["share_quote"] == "金句"
    assert (await user_repo.get_by_id(user_id)).total_xp == 12


async def test_complete_quiz_twice_does_not_double_xp(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_repo = UserRepository(mysql_db)
    user_id = await create_user(mysql_db)

    first = await repo.complete_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=12,
    )
    second = await repo.complete_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=12,
    )

    assert first is True
    assert second is False
    assert (await user_repo.get_by_id(user_id)).total_xp == 12


async def test_profile_stats_aggregate_across_quizzes(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)

    await repo.complete_quiz(
        quiz_id="quiz_a",
        user_id=user_id,
        records=RECORDS,
        total_questions=5,
        correct_count=4,
        accuracy=80.0,
        report=REPORT,
        xp_gained=18,
    )
    await repo.complete_quiz(
        quiz_id="quiz_b",
        user_id=user_id,
        records=RECORDS,
        total_questions=5,
        correct_count=5,
        accuracy=100.0,
        report=REPORT,
        xp_gained=20,
    )

    stats = await repo.get_profile_stats(user_id)

    assert stats["quiz_count"] == 2
    assert stats["correct_count"] == 9
    assert stats["average_accuracy"] == 90


async def test_profile_stats_are_zero_for_new_user(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)

    stats = await repo.get_profile_stats(user_id)

    assert stats == {"quiz_count": 0, "correct_count": 0, "average_accuracy": 0}


async def test_list_quizzes_paginates_newest_first(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)

    for index in range(3):
        await repo.complete_quiz(
            quiz_id=f"quiz_{index}",
            user_id=user_id,
            records=RECORDS,
            total_questions=1,
            correct_count=1,
            accuracy=100.0,
            report=REPORT,
            xp_gained=12,
        )

    items, total = await repo.list_quizzes(user_id=user_id, page=1, page_size=2)

    assert total == 3
    assert len(items) == 2
    assert items[0]["quiz_id"] == "quiz_2"
    assert items[1]["quiz_id"] == "quiz_1"


async def test_list_quizzes_isolated_between_users(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_repo = UserRepository(mysql_db)
    user_a = (await user_repo.create(openid="openid-a")).id
    user_b = (await user_repo.create(openid="openid-b")).id

    await repo.complete_quiz(
        quiz_id="quiz_a1",
        user_id=user_a,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=12,
    )

    items_b, total_b = await repo.list_quizzes(user_id=user_b, page=1, page_size=10)
    items_a, total_a = await repo.list_quizzes(user_id=user_a, page=1, page_size=10)

    assert total_b == 0 and items_b == []
    assert total_a == 1 and items_a[0]["quiz_id"] == "quiz_a1"


async def test_get_quiz_detail_bundles_records_and_report(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)

    await repo.save_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        title="RAG 入门",
        summary="摘要",
        user_input="RAG",
        questions=QUESTIONS,
    )
    await repo.complete_quiz(
        quiz_id="quiz_1",
        user_id=user_id,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=12,
    )

    detail = await repo.get_quiz_detail(quiz_id="quiz_1", user_id=user_id)

    assert detail is not None
    assert detail["title"] == "RAG 入门"
    assert detail["questions"][0]["id"] == "q1"
    assert detail["answer_records"] == RECORDS
    assert detail["report"]["accuracy"] == 100


async def test_get_quiz_detail_rejects_other_user(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_repo = UserRepository(mysql_db)
    owner = (await user_repo.create(openid="openid-owner")).id
    other = (await user_repo.create(openid="openid-other")).id

    await repo.save_quiz(
        quiz_id="quiz_1",
        user_id=owner,
        title="RAG 入门",
        summary="摘要",
        user_input="RAG",
        questions=QUESTIONS,
    )

    assert await repo.get_quiz_detail(quiz_id="quiz_1", user_id=other) is None
