from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.llm.schemas import (
    QuestionDraft,
    QuestionOptionDraft,
    QuizDraft,
    ReportDraft,
)
from app.main import create_app

TOPIC = "RAG 和传统搜索有什么区别"


def build_question_draft(index: int, question_type: str, topic: str = TOPIC) -> QuestionDraft:
    if question_type == "judge":
        options = [
            QuestionOptionDraft(key="A", text="正确"),
            QuestionOptionDraft(key="B", text="错误"),
        ]
        answer = ["A"]
    elif question_type == "multiple":
        options = [
            QuestionOptionDraft(key="A", text="检索增强生成"),
            QuestionOptionDraft(key="B", text="纯关键词匹配"),
            QuestionOptionDraft(key="C", text="向量召回"),
            QuestionOptionDraft(key="D", text="只能在离线环境使用"),
        ]
        answer = ["A", "C"]
    else:
        options = [
            QuestionOptionDraft(key="A", text="正确说法"),
            QuestionOptionDraft(key="B", text="错误说法一"),
            QuestionOptionDraft(key="C", text="错误说法二"),
            QuestionOptionDraft(key="D", text="错误说法三"),
        ]
        answer = ["A"]

    return QuestionDraft(
        type=question_type,
        stem=f"第 {index} 题：关于 {topic} 的说法，哪一项是成立的？",
        options=options,
        answer=answer,
        explanation=f"解析：第 {index} 题围绕 {topic} 的核心概念展开，注意区分检索与生成两个阶段。",
        knowledge_point=f"知识点 {index}",
        difficulty="easy",
    )


def question_type_plan(count: int) -> list[str]:
    plan = ["single", "single", "single", "multiple", "judge"]
    if count <= len(plan):
        return plan[:count]
    while len(plan) < count:
        plan.append("single")
    return plan


def build_quiz_draft(count: int = 5, topic: str = TOPIC) -> QuizDraft:
    questions = [
        build_question_draft(index, question_type, topic)
        for index, question_type in enumerate(question_type_plan(count), start=1)
    ]
    return QuizDraft(
        title=f"{topic[:12]} 闯关",
        summary=f"围绕 {topic} 生成的闯关题库",
        questions=questions,
    )


def build_report_draft() -> ReportDraft:
    return ReportDraft(
        three_line_summary=["第一句总结", "第二句总结", "第三句总结"],
        advice=["建议一", "建议二"],
        share_quote="把知识做成关卡，记忆会更深。",
    )


class FakeProvider:
    """Deterministic provider used by unit tests, records every call."""

    def __init__(
        self,
        quiz_drafts: list[QuizDraft] | None = None,
        report_draft: ReportDraft | None = None,
        quiz_error: Exception | None = None,
        report_error: Exception | None = None,
    ) -> None:
        self._quiz_drafts = list(quiz_drafts or [])
        self._report_draft = report_draft or build_report_draft()
        self._quiz_error = quiz_error
        self._report_error = report_error
        self.quiz_calls: list[dict[str, Any]] = []
        self.report_calls: list[dict[str, Any]] = []

    async def generate_quiz(
        self,
        *,
        topic: str,
        question_count: int,
        difficulty: str,
        strict: bool = False,
    ) -> QuizDraft:
        self.quiz_calls.append(
            {
                "topic": topic,
                "question_count": question_count,
                "difficulty": difficulty,
                "strict": strict,
            }
        )
        if self._quiz_error is not None:
            raise self._quiz_error
        if self._quiz_drafts:
            return self._quiz_drafts.pop(0)
        return build_quiz_draft(question_count, topic)

    async def generate_report(
        self,
        *,
        topic: str,
        quiz_summary: str,
        question_results: list[dict[str, Any]],
        stats: dict[str, Any],
        strict: bool = False,
    ) -> ReportDraft:
        self.report_calls.append(
            {
                "topic": topic,
                "quiz_summary": quiz_summary,
                "question_results": question_results,
                "stats": stats,
                "strict": strict,
            }
        )
        if self._report_error is not None:
            raise self._report_error
        return self._report_draft


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        rate_limit_enabled=False,
    )


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(settings: Settings, provider: FakeProvider) -> Iterator[TestClient]:
    app = create_app(settings=settings, provider=provider)
    with TestClient(app) as test_client:
        yield test_client
