"""LLM 提供方协议。"""

from __future__ import annotations

from typing import Any, Protocol

from app.llm.schemas import QuizDraft, ReportDraft


class LearningAIProvider(Protocol):
    async def generate_quiz(
        self,
        *,
        topic: str,
        question_count: int,
        difficulty: str,
        strict: bool = False,
    ) -> QuizDraft: ...

    async def generate_report(
        self,
        *,
        topic: str,
        quiz_summary: str,
        question_results: list[dict[str, Any]],
        stats: dict[str, Any],
        strict: bool = False,
    ) -> ReportDraft: ...
