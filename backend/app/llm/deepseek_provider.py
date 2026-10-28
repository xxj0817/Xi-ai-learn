"""DeepSeek（OpenAI 兼容）Provider，基于 LangChain 结构化输出。"""

from __future__ import annotations

import logging
from typing import Any, Sequence, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.core.exceptions import AIProviderError
from app.llm.model_factory import build_deepseek_chat_model
from app.llm.prompt_builder import build_chat_prompt
from app.llm.schemas import QuizDraft, ReportDraft
from app.models.quiz import QuizSource
from app.prompts.quiz_prompt import build_quiz_messages
from app.prompts.report_prompt import build_report_messages

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class DeepSeekProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_quiz(
        self,
        *,
        topic: str,
        question_count: int,
        difficulty: str,
        sources: Sequence[QuizSource] = (),
        strict: bool = False,
    ) -> QuizDraft:
        messages = build_quiz_messages(
            topic,
            question_count=question_count,
            difficulty=difficulty,
            sources=sources,
            strict=strict,
            source_total_max_chars=self._settings.source_total_max_chars,
        )
        return await self._invoke(
            QuizDraft,
            messages,
            temperature=self._settings.quiz_temperature,
            max_tokens=self._settings.quiz_max_tokens,
        )

    async def generate_report(
        self,
        *,
        topic: str,
        quiz_summary: str,
        question_results: list[dict[str, Any]],
        stats: dict[str, Any],
        strict: bool = False,
    ) -> ReportDraft:
        messages = build_report_messages(
            topic=topic,
            quiz_summary=quiz_summary,
            question_results=question_results,
            stats=stats,
            strict=strict,
        )
        return await self._invoke(
            ReportDraft,
            messages,
            temperature=self._settings.report_temperature,
            max_tokens=self._settings.report_max_tokens,
        )

    def _build_model(self, *, temperature: float, max_tokens: int) -> ChatOpenAI:
        return build_deepseek_chat_model(
            self._settings,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def _invoke(
        self,
        schema: type[SchemaT],
        messages: list[tuple[str, str]],
        *,
        temperature: float,
        max_tokens: int,
    ) -> SchemaT:
        model = self._build_model(temperature=temperature, max_tokens=max_tokens)
        last_error: object = None

        for method in ("function_calling", "json_mode"):
            try:
                structured = model.with_structured_output(schema, method=method, include_raw=True)
                chain = build_chat_prompt(messages) | structured
                result = await chain.ainvoke({})
                parsed = result.get("parsed") if isinstance(result, dict) else result
                if parsed is not None:
                    return parsed
                last_error = result.get("parsing_error") if isinstance(result, dict) else "empty result"
                logger.warning("DeepSeek 结构化输出为空 method=%s", method)
            except Exception as exc:  # noqa: BLE001 - 需要兜底切换解析策略
                last_error = exc
                logger.warning("DeepSeek 调用失败 method=%s error=%s", method, type(exc).__name__)

        cause = (
            last_error
            if isinstance(last_error, BaseException)
            else Exception(str(last_error or "结构化输出解析失败"))
        )
        raise AIProviderError() from cause
