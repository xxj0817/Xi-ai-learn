"""DeepSeek（OpenAI 兼容）Provider，基于 LangChain 结构化输出。"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

import httpx
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from app.core.config import Settings
from app.core.exceptions import AIProviderError
from app.llm.prompt_builder import build_chat_prompt
from app.llm.schemas import QuizDraft, ReportDraft
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
        strict: bool = False,
    ) -> QuizDraft:
        messages = build_quiz_messages(
            topic,
            question_count=question_count,
            difficulty=difficulty,
            strict=strict,
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

    def _build_http_client(self) -> httpx.AsyncClient:
        proxy_url = self._settings.deepseek_proxy_url.strip()
        timeout = self._settings.deepseek_timeout_seconds
        if proxy_url:
            return httpx.AsyncClient(proxy=proxy_url, trust_env=False, timeout=timeout)
        return httpx.AsyncClient(trust_env=self._settings.deepseek_trust_env_proxy, timeout=timeout)

    def _build_model(self, *, temperature: float, max_tokens: int) -> ChatOpenAI:
        thinking = "enabled" if self._settings.deepseek_thinking_enabled else "disabled"
        return ChatOpenAI(
            model=self._settings.deepseek_model,
            base_url=self._settings.deepseek_base_url,
            api_key=SecretStr(self._settings.deepseek_api_key),
            temperature=temperature,
            top_p=self._settings.llm_top_p,
            max_tokens=max_tokens,
            timeout=self._settings.deepseek_timeout_seconds,
            max_retries=0,
            extra_body={"thinking": {"type": thinking}},
            http_async_client=self._build_http_client(),
            # 显式禁用内置 socket 选项，避免 langchain-openai 注入自定义 transport
            # 时产生“代理被屏蔽”的误导性告警；连接策略完全由 _build_http_client 决定。
            http_socket_options=(),
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
