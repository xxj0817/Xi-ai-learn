"""官方 LangChain Tavily 工具套件与薄适配层。"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from langchain_tavily import TavilyExtract, TavilySearch

from app.core.config import Settings
from app.search.source_collector import SourceCollector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolPreset:
    name: str
    kind: str
    scope: str
    max_results: int | None
    include_raw_content: bool | str
    country: str | None


@dataclass(frozen=True)
class TavilyToolSuite:
    tools: list[BaseTool]
    collector: SourceCollector
    country: str | None
    has_local_tools: bool
    prefer_sync: bool
    presets: dict[str, ToolPreset]


def configure_tavily_proxy_env(settings: Settings) -> None:
    """官方同步路径使用 requests，会读取这些进程级代理变量。"""
    proxy = settings.tavily_proxy_url.strip()
    if not proxy:
        return
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ[name] = proxy


def build_tavily_toolset(
    settings: Settings,
    *,
    collector: SourceCollector,
    country: str | None = None,
) -> TavilyToolSuite:
    if not settings.web_search_enabled or settings.web_search_provider != "tavily":
        raise RuntimeError("联网检索未启用")
    if not settings.tavily_api_key.strip():
        raise RuntimeError("未配置 TAVILY_API_KEY")

    configure_tavily_proxy_env(settings)
    prefer_sync = bool(settings.tavily_proxy_url.strip()) or settings.tavily_trust_env_proxy
    tools: list[BaseTool] = []
    presets: dict[str, ToolPreset] = {}

    def add_search(
        *,
        name: str,
        description: str,
        scope: str,
        max_results: int,
        search_depth: str,
        include_raw_content: bool | str,
        search_country: str | None,
    ) -> None:
        inner = TavilySearch(
            name=name,
            description=description,
            tavily_api_key=settings.tavily_api_key,
            api_base_url=settings.tavily_base_url,
            max_results=max_results,
            search_depth=search_depth,
            include_raw_content=include_raw_content,
            include_answer=False,
            country=search_country,
        )
        tools.append(
            wrap_tool(
                inner,
                name=name,
                description=description,
                collector=collector,
                timeout_seconds=settings.tavily_tool_timeout_seconds,
                prefer_sync=prefer_sync,
            )
        )
        presets[name] = ToolPreset(
            name=name,
            kind="search",
            scope=scope,
            max_results=max_results,
            include_raw_content=include_raw_content,
            country=search_country,
        )

    if country:
        add_search(
            name="tavily_search_quick_local",
            description=(
                "快速网络搜索，返回摘要片段，适合概念简单、事实稳定的本地主题。"
                f"固定返回 {settings.tavily_quick_max_results} 条结果。"
            ),
            scope="local",
            max_results=settings.tavily_quick_max_results,
            search_depth=settings.tavily_quick_search_depth,
            include_raw_content=False,
            search_country=country,
        )
        add_search(
            name="tavily_search_deep_local",
            description=(
                "深度网络搜索，返回整页正文，适合新概念、冷门、复杂或可能超出训练语料的本地主题。"
                f"固定返回 {settings.tavily_deep_max_results} 条结果。"
            ),
            scope="local",
            max_results=settings.tavily_deep_max_results,
            search_depth=settings.tavily_deep_search_depth,
            include_raw_content=settings.tavily_deep_include_raw_content,
            search_country=country,
        )

    add_search(
        name="tavily_search_quick_global",
        description=(
            "快速全球搜索，返回摘要片段，适合概念简单、事实稳定的国际主题。"
            f"固定返回 {settings.tavily_quick_max_results} 条结果。"
        ),
        scope="global",
        max_results=settings.tavily_quick_max_results,
        search_depth=settings.tavily_quick_search_depth,
        include_raw_content=False,
        search_country=None,
    )
    add_search(
        name="tavily_search_deep_global",
        description=(
            "深度全球搜索，返回整页正文，适合新概念、冷门、复杂或可能超出训练语料的国际主题。"
            f"固定返回 {settings.tavily_deep_max_results} 条结果。"
        ),
        scope="global",
        max_results=settings.tavily_deep_max_results,
        search_depth=settings.tavily_deep_search_depth,
        include_raw_content=settings.tavily_deep_include_raw_content,
        search_country=None,
    )

    extract_description = (
        "提取指定网址的整页正文；用户提供网址时必须优先使用。"
        "传 query 可聚焦相关段落，不传则返回整页内容。"
    )
    extract_inner = TavilyExtract(
        name="tavily_extract_page",
        description=extract_description,
        tavily_api_key=settings.tavily_api_key,
        api_base_url=settings.tavily_base_url,
        format=settings.tavily_extract_format,
        chunks_per_source=settings.tavily_extract_chunks_per_source,
        include_images=False,
    )
    tools.append(
        wrap_tool(
            extract_inner,
            name="tavily_extract_page",
            description=extract_description,
            collector=collector,
            timeout_seconds=settings.tavily_tool_timeout_seconds,
            prefer_sync=prefer_sync,
        )
    )
    presets["tavily_extract_page"] = ToolPreset(
        name="tavily_extract_page",
        kind="extract",
        scope="global",
        max_results=None,
        include_raw_content=True,
        country=None,
    )

    logger.info(
        "Tavily 工具套件就绪 tools=%s local=%s prefer_sync=%s",
        len(tools),
        bool(country),
        prefer_sync,
    )
    return TavilyToolSuite(
        tools=tools,
        collector=collector,
        country=country,
        has_local_tools=bool(country),
        prefer_sync=prefer_sync,
        presets=presets,
    )


def wrap_tool(
    inner: BaseTool,
    *,
    name: str,
    description: str,
    collector: SourceCollector,
    timeout_seconds: float,
    prefer_sync: bool,
) -> BaseTool:
    def _call(**kwargs: Any) -> Any:
        try:
            result = inner.invoke(kwargs)
        except Exception as exc:  # noqa: BLE001 - 工具失败交给 Agent 自行判断
            logger.warning("Tavily 工具调用失败 tool=%s error=%s", name, type(exc).__name__)
            return {"error": type(exc).__name__}
        return collector.record(name, result)

    async def _acall(**kwargs: Any) -> Any:
        try:
            if prefer_sync:
                result = await asyncio.wait_for(
                    asyncio.to_thread(inner.invoke, kwargs),
                    timeout=timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    inner.ainvoke(kwargs),
                    timeout=timeout_seconds,
                )
        except asyncio.TimeoutError:
            logger.warning("Tavily 工具调用超时 tool=%s", name)
            return {"error": "TimeoutError"}
        except Exception as exc:  # noqa: BLE001 - 工具失败交给 Agent 自行判断
            logger.warning("Tavily 工具调用失败 tool=%s error=%s", name, type(exc).__name__)
            return {"error": type(exc).__name__}
        return collector.record(name, result)

    return StructuredTool.from_function(
        func=_call,
        coroutine=_acall,
        name=name,
        description=description,
        args_schema=inner.args_schema,
    )
