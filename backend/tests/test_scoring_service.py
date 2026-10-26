from __future__ import annotations

import pytest

from app.core.exceptions import InvalidInput
from app.models.quiz import Question, QuestionOption
from app.models.report import AnswerRecord
from app.services.scoring_service import build_score_summary


def question(
    question_id: str,
    answer: list[str],
    knowledge_point: str,
    question_type: str = "single",
) -> Question:
    options = [QuestionOption(key="A", text="选项 A"), QuestionOption(key="B", text="选项 B")]
    if question_type == "multiple":
        options.append(QuestionOption(key="C", text="选项 C"))
    return Question(
        id=question_id,
        type=question_type,
        stem=f"{question_id} 的题干",
        options=options,
        answer=answer,
        explanation="解析",
        knowledge_point=knowledge_point,
        difficulty="easy",
    )


def record(
    question_id: str,
    selected: list[str],
    *,
    is_correct: bool | None = None,
    duration_ms: int = 3000,
) -> AnswerRecord:
    return AnswerRecord(
        question_id=question_id,
        selected_answers=selected,
        is_correct=is_correct,
        duration_ms=duration_ms,
    )


QUESTIONS = [
    question("q1", ["A"], "检索流程"),
    question("q2", ["A", "C"], "向量召回", "multiple"),
    question("q3", ["B"], "生成阶段"),
]


def test_scoring_ignores_client_reported_correctness() -> None:
    records = [
        record("q1", ["B"], is_correct=True),
        record("q2", ["A", "C"], is_correct=False),
        record("q3", ["B"], is_correct=False),
    ]

    summary = build_score_summary(QUESTIONS, records)

    assert summary.correct == 2
    assert summary.total == 3
    assert summary.accuracy == 67
    assert summary.mastered_points == ["向量召回", "生成阶段"]
    assert summary.weak_points == ["检索流程"]


def test_multiple_choice_requires_exact_match() -> None:
    records = [
        record("q1", ["A"]),
        record("q2", ["A"]),
        record("q3", ["B"]),
    ]

    summary = build_score_summary(QUESTIONS, records)

    assert summary.correct == 2
    assert summary.results[1].is_correct is False


def test_accuracy_rounding() -> None:
    records = [
        record("q1", ["A"]),
        record("q2", ["A", "C"]),
        record("q3", ["A"]),
    ]

    summary = build_score_summary(QUESTIONS, records)

    assert summary.accuracy == 67


def test_all_correct_has_no_weak_points() -> None:
    records = [record("q1", ["A"]), record("q2", ["A", "C"]), record("q3", ["B"])]

    summary = build_score_summary(QUESTIONS, records)

    assert summary.accuracy == 100
    assert summary.weak_points == []
    assert summary.mastered_points == ["检索流程", "向量召回", "生成阶段"]


def test_knowledge_points_are_deduplicated() -> None:
    questions = [
        question("q1", ["A"], "检索流程"),
        question("q2", ["B"], "检索流程"),
        question("q3", ["A"], "生成阶段"),
    ]
    records = [record("q1", ["B"]), record("q2", ["A"]), record("q3", ["A"])]

    summary = build_score_summary(questions, records)

    assert summary.weak_points == ["检索流程"]
    assert summary.mastered_points == ["生成阶段"]


def test_missing_answer_record_is_rejected() -> None:
    with pytest.raises(InvalidInput):
        build_score_summary(QUESTIONS, [record("q1", ["A"]), record("q2", ["A", "C"])])


def test_unknown_question_id_is_rejected() -> None:
    with pytest.raises(InvalidInput):
        build_score_summary(
            QUESTIONS,
            [record("q1", ["A"]), record("q2", ["A", "C"]), record("q404", ["B"])],
        )


def test_duplicate_answer_record_is_rejected() -> None:
    with pytest.raises(InvalidInput):
        build_score_summary(
            QUESTIONS,
            [record("q1", ["A"]), record("q1", ["A"]), record("q2", ["A", "C"]), record("q3", ["B"])],
        )


def test_empty_selection_is_rejected() -> None:
    with pytest.raises(InvalidInput):
        build_score_summary(QUESTIONS, [record("q1", []), record("q2", ["A", "C"]), record("q3", ["B"])])


def test_selection_outside_options_is_rejected() -> None:
    with pytest.raises(InvalidInput):
        build_score_summary(QUESTIONS, [record("q1", ["Z"]), record("q2", ["A", "C"]), record("q3", ["B"])])


def test_result_payload_contains_question_snapshot() -> None:
    records = [record("q1", ["B"]), record("q2", ["A", "C"]), record("q3", ["B"])]

    summary = build_score_summary(QUESTIONS, records)

    first = summary.results[0]
    assert first.question_id == "q1"
    assert first.correct_answer == ["A"]
    assert first.selected_answers == ["B"]
    assert first.knowledge_point == "检索流程"
    assert first.stem == "q1 的题干"
