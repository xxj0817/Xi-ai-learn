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
PROGRESS_RECORDS = [
    {"question_id": "q1", "selected": ["A"], "is_correct": True, "duration_ms": 900},
]


async def test_save_progress_upserts_and_lists_in_progress(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)
    await repo.save_quiz(
        quiz_id="quiz_progress_1",
        user_id=user_id,
        title="未完成关卡",
        summary="摘要",
        user_input="RAG",
        questions=QUESTIONS,
    )

    assert (
        await repo.save_progress(
            quiz_id="quiz_progress_1",
            user_id=user_id,
            records=PROGRESS_RECORDS,
            answered_count=1,
        )
        is True
    )
    rows = await repo.list_in_progress(user_id=user_id, limit=10)

    assert len(rows) == 1
    assert rows[0]["quiz_id"] == "quiz_progress_1"
    assert rows[0]["answered_count"] == 1
    assert rows[0]["question_count"] == 1
    assert await repo.get_progress("quiz_progress_1") == PROGRESS_RECORDS


async def test_save_progress_rejects_other_user(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    owner_id = await create_user(mysql_db)
    await repo.save_quiz(
        quiz_id="quiz_progress_2",
        user_id=owner_id,
        title="私有闯关",
        summary="",
        user_input="RAG",
        questions=QUESTIONS,
    )

    assert (
        await repo.save_progress(
            quiz_id="quiz_progress_2",
            user_id=owner_id + 999,
            records=PROGRESS_RECORDS,
            answered_count=1,
        )
        is False
    )


async def test_completing_quiz_clears_progress(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)
    await repo.save_quiz(
        quiz_id="quiz_progress_3",
        user_id=user_id,
        title="未完成关卡",
        summary="",
        user_input="RAG",
        questions=QUESTIONS,
    )
    await repo.save_progress(
        quiz_id="quiz_progress_3",
        user_id=user_id,
        records=PROGRESS_RECORDS,
        answered_count=1,
    )

    await repo.complete_quiz(
        quiz_id="quiz_progress_3",
        user_id=user_id,
        records=RECORDS,
        total_questions=1,
        correct_count=1,
        accuracy=100.0,
        report=REPORT,
        xp_gained=12,
    )
    rows = await repo.list_in_progress(user_id=user_id, limit=10)

    assert rows == []
    assert await repo.get_progress("quiz_progress_3") == []

async def test_held_connection_reads_latest_committed_data() -> None:
    """回归：只读连接不能长期持有旧快照，否则新写入的关卡查不到。"""
    from app.core.db import Database
    from tests.conftest import integration_mysql_settings

    settings = integration_mysql_settings("xi_ai_learn_test")
    if settings is None:
        pytest.skip(".env 不存在，跳过 MySQL 集成测试")
    settings.mysql_pool_min_size = 1
    settings.mysql_pool_max_size = 2

    database = Database(settings)
    try:
        await database.connect()
    except Exception as exc:  # noqa: BLE001 - 本机无 MySQL 时跳过
        pytest.skip(f"MySQL 不可用，跳过集成测试：{type(exc).__name__}")

    sql = "SELECT COUNT(*) FROM quiz_sessions WHERE user_id = %s"
    try:
        async with database.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for table in ("quiz_progress", "answer_records", "reports", "quiz_sessions", "users"):
                    await cursor.execute(f"DELETE FROM {table}")

        repo = QuizRepository(database)
        user_repo = UserRepository(database)
        user = await user_repo.create(openid="openid-stale-read")

        async with database.pool.acquire() as reader:
            async with reader.cursor() as cursor:
                await cursor.execute(sql, (user.id,))
                assert int((await cursor.fetchone())[0]) == 0

            await repo.save_quiz(
                quiz_id="quiz_stale_read",
                user_id=user.id,
                title="新写入的关卡",
                summary="",
                user_input="RAG",
                questions=QUESTIONS,
            )

            async with reader.cursor() as cursor:
                await cursor.execute(sql, (user.id,))
                assert int((await cursor.fetchone())[0]) == 1
    finally:
        await database.close()


async def test_save_grounding_is_idempotent_and_detail_returns_it(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)
    await repo.save_quiz(
        quiz_id="quiz_grounding_1",
        user_id=user_id,
        title="Harness Engineering",
        summary="摘要",
        user_input="Harness Engineering",
        questions=QUESTIONS,
    )
    sources = [
        {
            "id": "S1",
            "title": "Harness Engineering",
            "url": "https://example.com/harness",
            "snippet": "AI Agent 工程实践",
            "origin": "web",
        }
    ]
    await repo.save_grounding(
        quiz_id="quiz_grounding_1",
        user_id=user_id,
        sources=sources,
        grounding={
            "status": "grounded",
            "provider": "tavily",
            "searched_at": "2026-10-28T10:00:00+00:00",
            "evidence_chars": 12,
        },
    )
    await repo.save_grounding(
        quiz_id="quiz_grounding_1",
        user_id=user_id,
        sources=sources,
        grounding={
            "status": "partial",
            "provider": "tavily",
            "searched_at": "2026-10-28T10:00:00+00:00",
            "evidence_chars": 12,
        },
    )

    detail = await repo.get_quiz_detail(quiz_id="quiz_grounding_1", user_id=user_id)

    assert detail is not None
    assert detail["grounding"]["status"] == "partial"
    assert detail["sources"][0]["id"] == "S1"


async def test_detail_without_grounding_returns_defaults(mysql_db: Database) -> None:
    repo = QuizRepository(mysql_db)
    user_id = await create_user(mysql_db)
    await repo.save_quiz(
        quiz_id="quiz_no_grounding",
        user_id=user_id,
        title="历史题库",
        summary="",
        user_input="RAG",
        questions=QUESTIONS,
    )

    detail = await repo.get_quiz_detail(quiz_id="quiz_no_grounding", user_id=user_id)

    assert detail is not None
    assert detail["sources"] == []
    assert detail["grounding"] == {}
