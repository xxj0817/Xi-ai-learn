"""LangChain 研究 Agent：自主选择 Tavily 工具并返回结构化研究结果。"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.tools import BaseTool

from app.core.config import Settings
from app.llm.model_factory import build_deepseek_chat_model
from app.llm.schemas import ResearchBrief
from app.prompts.research_prompt import (
    build_research_system_prompt,
    build_research_user_message,
)
from app.services.region_resolver import RegionContext

logger = logging.getLogger(__name__)


class ResearchAgentUnavailable(RuntimeError):
    """当前配置无法运行研究 Agent。"""


class ResearchAgent:
    def __init__(self, settings: Settings) -> None:
        if settings.llm_provider != "deepseek" or not settings.deepseek_api_key.strip():
            raise ResearchAgentUnavailable("研究 Agent 需要 deepseek 提供方与有效 API Key")
        self._settings = settings
        self._model = build_deepseek_chat_model(
            settings,
            temperature=settings.research_temperature,
            max_tokens=settings.research_max_tokens,
        )

    async def run(
        self,
        *,
        tools: Sequence[BaseTool],
        user_input: str,
        urls: list[str],
        source_text: str,
        region: RegionContext,
    ) -> ResearchBrief:
        today = date.today()
        system_prompt = build_research_system_prompt(
            today=today,
            region_label=region.label,
            locale=region.locale,
            has_local_tools=region.country is not None,
        )
        user_message = build_research_user_message(
            user_input=user_input,
            urls=urls,
            source_text=source_text,
            region_label=region.label,
            today=today,
        )
        agent = create_agent(
            self._model,
            list(tools),
            system_prompt=system_prompt,
            response_format=ResearchBrief,
            middleware=[
                ModelCallLimitMiddleware(
                    run_limit=self._settings.research_agent_max_model_calls,
                    exit_behavior="end",
                ),
                ToolCallLimitMiddleware(
                    run_limit=self._settings.research_agent_max_tool_calls,
                    exit_behavior="end",
                ),
            ],
        )
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [{"role": "user", "content": user_message}]},
                config={"recursion_limit": self._settings.research_agent_recursion_limit},
            ),
            timeout=self._settings.research_agent_timeout_seconds,
        )

        structured = result.get("structured_response") if isinstance(result, dict) else None
        if isinstance(structured, ResearchBrief):
            return structured
        if isinstance(structured, dict):
            return ResearchBrief.model_validate(structured)
        logger.warning("研究 Agent 未返回结构化结果")
        return ResearchBrief()
