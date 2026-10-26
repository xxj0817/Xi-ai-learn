from __future__ import annotations

from app.prompts.quiz_prompt import QUIZ_PROMPT_VERSION, build_quiz_messages
from app.prompts.report_prompt import REPORT_PROMPT_VERSION, build_report_messages


def test_quiz_prompt_version() -> None:
    assert QUIZ_PROMPT_VERSION == "quiz_prompt_v1"


def test_report_prompt_version() -> None:
    assert REPORT_PROMPT_VERSION == "report_prompt_v1"


def test_quiz_prompt_requires_structured_json() -> None:
    messages = build_quiz_messages("RAG 是什么", question_count=5, difficulty="mixed")
    system = messages[0][1]

    assert "JSON" in system
    assert "不要输出 Markdown" in system
    for field in ("stem", "options", "answer", "explanation", "knowledge_point", "difficulty", "type"):
        assert field in system
    assert "single" in system
    assert "multiple" in system
    assert "judge" in system
    assert "5" in system


def test_quiz_prompt_embeds_user_input() -> None:
    messages = build_quiz_messages("我想学习 RAG 的检索流程", question_count=5, difficulty="mixed")

    assert messages[0][0] == "system"
    assert messages[1][0] == "user"
    assert "我想学习 RAG 的检索流程" in messages[1][1]


def test_quiz_prompt_strict_mode_adds_guardrails() -> None:
    normal = build_quiz_messages("RAG", question_count=5, difficulty="mixed")
    strict = build_quiz_messages("RAG", question_count=5, difficulty="mixed", strict=True)

    assert strict[0][1] != normal[0][1]
    assert "严格" in strict[0][1]


def test_report_prompt_requires_structured_json() -> None:
    messages = build_report_messages(
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
        stats={"accuracy": 40, "correct": 2, "total": 5, "mastered_points": [], "weak_points": ["检索流程"]},
    )
    system = messages[0][1]
    user = messages[1][1]

    assert REPORT_PROMPT_VERSION == "report_prompt_v1"
    assert "JSON" in system
    assert "不要输出 Markdown" in system
    for field in ("three_line_summary", "advice", "share_quote"):
        assert field in system
    assert "RAG 入门" in user
    assert "检索流程" in user
    assert "40" in user
    assert "不要编造" in system
