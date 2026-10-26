from __future__ import annotations

import asyncio

from app.llm.mock_provider import MockProvider
from app.services.quiz_normalizer import normalize_quiz


def run(coroutine):
    return asyncio.run(coroutine)


def test_mock_quiz_has_expected_type_distribution() -> None:
    provider = MockProvider()

    draft = run(provider.generate_quiz(topic="RAG 入门", question_count=5, difficulty="mixed"))

    assert len(draft.questions) == 5
    types = [question.type for question in draft.questions]
    assert types.count("single") == 3
    assert types.count("multiple") == 1
    assert types.count("judge") == 1


def test_mock_quiz_passes_normalization() -> None:
    provider = MockProvider()
    draft = run(provider.generate_quiz(topic="RAG 入门", question_count=5, difficulty="mixed"))

    quiz = normalize_quiz(
        draft,
        quiz_id="quiz_mock",
        user_input="RAG 入门",
        expected_count=5,
    )

    assert len(quiz.questions) == 5
    for question in quiz.questions:
        assert question.options
        assert question.answer
        assert set(question.answer).issubset({option.key for option in question.options})
        assert question.explanation


def test_mock_quiz_supports_other_counts() -> None:
    provider = MockProvider()

    for count in (3, 4, 6, 8):
        draft = run(provider.generate_quiz(topic="提示词工程", question_count=count, difficulty="easy"))
        assert len(draft.questions) == count


def test_mock_quiz_is_deterministic() -> None:
    provider = MockProvider()

    first = run(provider.generate_quiz(topic="RAG", question_count=5, difficulty="mixed"))
    second = run(provider.generate_quiz(topic="RAG", question_count=5, difficulty="mixed"))

    assert [question.stem for question in first.questions] == [question.stem for question in second.questions]


def test_mock_quiz_mentions_topic_in_title() -> None:
    provider = MockProvider()

    draft = run(provider.generate_quiz(topic="向量数据库怎么用", question_count=5, difficulty="mixed"))

    assert "向量数据库" in draft.title


def test_mock_report_is_complete() -> None:
    provider = MockProvider()

    report = run(
        provider.generate_report(
            topic="RAG 入门",
            quiz_summary="围绕 RAG 生成的题库",
            question_results=[
                {
                    "question_id": "q1",
                    "stem": "题干",
                    "knowledge_point": "检索流程",
                    "correct": False,
                    "selected_answers": ["B"],
                    "correct_answer": ["A"],
                }
            ],
            stats={
                "accuracy": 40,
                "correct": 2,
                "total": 5,
                "mastered_points": ["生成阶段"],
                "weak_points": ["检索流程"],
            },
        )
    )

    assert len(report.three_line_summary) == 3
    assert report.advice
    assert report.share_quote
