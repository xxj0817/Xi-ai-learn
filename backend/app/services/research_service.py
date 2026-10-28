"""研究服务：用户资料优先，Agent 自主检索，失败静默降级。"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol, Sequence

from app.core.config import Settings
from app.llm.schemas import ResearchBrief
from app.models.quiz import QuizSource, SourceOrigin
from app.search.cache import TTLCache
from app.search.source_collector import SourceCollector
from app.services.input_normalizer import merge_source_urls, strip_urls
from app.services.region_resolver import RegionContext, resolve_region

logger = logging.getLogger(__name__)


class ResearchAgentProtocol(Protocol):
    async def run(
        self,
        *,
        tools: Sequence[Any],
        user_input: str,
        urls: list[str],
        source_text: str,
        region: RegionContext,
    ) -> ResearchBrief: ...


@dataclass(frozen=True)
class ResearchResult:
    topic: str
    sources: list[QuizSource]
    provider: str
    searched_at: str | None
    evidence_chars: int
    mode: str


class ResearchService:
    def __init__(
        self,
        settings: Settings,
        *,
        agent: ResearchAgentProtocol | None = None,
        cache: TTLCache[ResearchResult] | None = None,
        toolset_builder: Callable[..., Any] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._cache = cache or TTLCache(settings.web_search_cache_ttl_seconds)
        self._toolset_builder = toolset_builder
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._search_configured = (
            settings.web_search_enabled
            and settings.web_search_provider == "tavily"
            and bool(settings.tavily_api_key.strip())
        )

    async def gather(
        self,
        *,
        user_input: str,
        source_text: str = "",
        source_urls: Sequence[str] = (),
        region: str | None = None,
        locale: str | None = None,
        accept_language: str | None = None,
    ) -> ResearchResult:
        user_input = (user_input or "").strip()
        source_text = source_text or ""
        urls = merge_source_urls(
            user_input,
            source_urls,
            max_urls=self._settings.user_source_max_urls,
        )
        region_context = resolve_region(
            region=region,
            locale=locale,
            accept_language=accept_language,
            user_input=user_input,
        )
        topic_hint = strip_urls(user_input)
        cache_key = self._cache_key(user_input, source_text, urls, region_context)

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("研究结果缓存命中 sources=%s", len(cached.sources))
            return ResearchResult(
                topic=cached.topic,
                sources=cached.sources,
                provider=cached.provider,
                searched_at=cached.searched_at,
                evidence_chars=cached.evidence_chars,
                mode="cache",
            )

        collector = self._make_collector()
        if source_text.strip():
            collector.add_user_text(source_text)

        if self._text_chars(source_text) >= self._settings.user_source_min_chars:
            return self._cache_and_return(
                cache_key,
                self._build_result(
                    topic=topic_hint or "学习主题",
                    sources=self._finalize(collector),
                    mode="user_only",
                    searched_at=None,
                ),
            )

        suite: Any | None = None
        if self._search_configured:
            try:
                suite = self._build_suite(collector, region_context)
            except Exception as exc:  # noqa: BLE001 - 检索不可用时降级
                logger.warning("Tavily 工具套件不可用 error=%s", type(exc).__name__)

        if suite is not None and urls:
            extracted_urls = await self._pre_extract(suite, urls)
            collector.mark_user_urls([*urls, *extracted_urls])

        user_sources = self._finalize(collector)
        user_evidence = sum(
            len(source.snippet)
            for source in user_sources
            if source.origin == SourceOrigin.user
        )
        if user_evidence >= self._settings.user_source_min_chars:
            return self._cache_and_return(
                cache_key,
                self._build_result(
                    topic=topic_hint or (user_sources[0].title if user_sources else "学习主题"),
                    sources=user_sources,
                    mode="user_only",
                    searched_at=None,
                ),
            )

        brief: ResearchBrief | None = None
        agent_attempted = False
        if suite is not None and self._agent is not None:
            agent_attempted = True
            try:
                brief = await self._agent.run(
                    tools=suite.tools,
                    user_input=user_input,
                    urls=urls,
                    source_text=source_text[:2000],
                    region=region_context,
                )
            except Exception as exc:  # noqa: BLE001 - Agent 失败进入降级
                logger.warning("研究 Agent 调用失败 error=%s", type(exc).__name__)

        topic = self._resolve_topic(brief, topic_hint, user_sources)
        used_urls = brief.used_urls if brief is not None else []
        sources = self._finalize(collector, used_urls=used_urls)
        if self._has_web_sources(sources):
            return self._cache_and_return(
                cache_key,
                self._build_result(
                    topic=topic,
                    sources=sources,
                    mode="agent" if brief is not None else "fallback",
                    searched_at=self._now_iso(),
                ),
            )

        if suite is not None and agent_attempted:
            await self._fallback_search(suite, topic_hint or user_input or topic)
            sources = self._finalize(collector)
            if self._has_web_sources(sources):
                return self._cache_and_return(
                    cache_key,
                    self._build_result(
                        topic=topic,
                        sources=sources,
                        mode="fallback",
                        searched_at=self._now_iso(),
                    ),
                )

        sources = self._finalize(collector)
        result = self._build_result(
            topic=topic,
            sources=sources,
            mode="user_only" if sources else "none",
            searched_at=None,
        )
        if sources:
            self._cache.set(cache_key, result)
        return result

    def _cache_key(
        self,
        user_input: str,
        source_text: str,
        urls: list[str],
        region: RegionContext,
    ) -> str:
        material = json.dumps(
            {"text": source_text, "urls": sorted(urls)},
            ensure_ascii=False,
            sort_keys=True,
        )
        raw = f"{region.country}|{region.locale}|{user_input}|{material}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _cache_and_return(self, key: str, result: ResearchResult) -> ResearchResult:
        self._cache.set(key, result)
        return result

    def _make_collector(self) -> SourceCollector:
        return SourceCollector(
            search_result_max_chars=self._settings.tavily_search_result_max_chars,
            extract_result_max_chars=self._settings.tavily_extract_result_max_chars,
            tool_total_max_chars=self._settings.tavily_tool_total_max_chars,
        )

    def _build_suite(self, collector: SourceCollector, region: RegionContext) -> Any:
        builder = self._toolset_builder
        if builder is None:
            from app.search.tavily_tools import build_tavily_toolset

            builder = build_tavily_toolset
        return builder(self._settings, collector=collector, country=region.country)

    async def _pre_extract(
        self,
        suite: Any,
        urls: list[str],
    ) -> list[str]:
        tool = self._find_tool(suite, "tavily_extract_page")
        if tool is None:
            return []
        payload: dict[str, Any] = {"urls": urls}
        try:
            result = await tool.ainvoke(payload)
            if isinstance(result, dict) and result.get("error"):
                logger.warning("用户网址提取失败 error=%s", result.get("error"))
                return []
            if isinstance(result, dict):
                return [
                    str(item.get("url"))
                    for item in result.get("results") or []
                    if isinstance(item, dict) and item.get("url")
                ]
        except Exception as exc:  # noqa: BLE001 - 用户链接失败不阻断
            logger.warning("用户网址提取失败 error=%s", type(exc).__name__)
        return []

    async def _fallback_search(self, suite: Any, query: str) -> None:
        tool = self._find_tool(suite, "tavily_search_quick_local") or self._find_tool(
            suite, "tavily_search_quick_global"
        )
        query = (query or "").strip()[:300]
        if tool is None or not query:
            return
        try:
            result = await tool.ainvoke({"query": query})
            if isinstance(result, dict) and result.get("error"):
                logger.warning("降级搜索失败 error=%s", result.get("error"))
        except Exception as exc:  # noqa: BLE001 - 降级失败保持静默
            logger.warning("降级搜索失败 error=%s", type(exc).__name__)

    def _find_tool(self, suite: Any, name: str) -> Any | None:
        for tool in getattr(suite, "tools", []):
            if getattr(tool, "name", "") == name:
                return tool
        return None

    def _finalize(
        self,
        collector: SourceCollector,
        *,
        used_urls: Sequence[str] = (),
    ) -> list[QuizSource]:
        return collector.finalize(
            used_urls=used_urls,
            max_sources=self._settings.web_search_max_sources,
            web_snippet_max_chars=self._settings.source_snippet_max_chars,
            user_snippet_max_chars=self._settings.user_source_snippet_max_chars,
            total_max_chars=self._settings.source_total_max_chars,
        )

    def _resolve_topic(
        self,
        brief: ResearchBrief | None,
        topic_hint: str,
        user_sources: Sequence[QuizSource],
    ) -> str:
        candidate = (brief.topic if brief is not None else "").strip()
        if candidate and not candidate.lower().startswith(("http://", "https://")):
            return candidate
        if topic_hint:
            return topic_hint
        if user_sources:
            return user_sources[0].title or "学习主题"
        return "学习主题"

    def _build_result(
        self,
        *,
        topic: str,
        sources: list[QuizSource],
        mode: str,
        searched_at: str | None,
    ) -> ResearchResult:
        has_user = any(source.origin == SourceOrigin.user for source in sources)
        has_web = any(source.origin == SourceOrigin.web for source in sources)
        if has_user and has_web:
            provider = "mixed"
        elif has_user:
            provider = "user"
        elif has_web:
            provider = "tavily"
        else:
            provider = "none"
        return ResearchResult(
            topic=topic or "学习主题",
            sources=sources,
            provider=provider,
            searched_at=searched_at if has_web else None,
            evidence_chars=sum(len(source.snippet) for source in sources),
            mode=mode,
        )

    def _has_web_sources(self, sources: Sequence[QuizSource]) -> bool:
        return any(source.origin == SourceOrigin.web for source in sources)

    def _now_iso(self) -> str:
        return self._now().astimezone(timezone.utc).isoformat()

    @staticmethod
    def _text_chars(text: str) -> int:
        return len(" ".join((text or "").split()))


def build_research_service(settings: Settings) -> ResearchService:
    agent: ResearchAgentProtocol | None = None
    search_ready = (
        settings.web_search_enabled
        and settings.web_search_provider == "tavily"
        and bool(settings.tavily_api_key.strip())
    )
    if (
        search_ready
        and settings.llm_provider == "deepseek"
        and settings.deepseek_api_key.strip()
    ):
        try:
            from app.agents.research_agent import ResearchAgent

            agent = ResearchAgent(settings)
        except Exception as exc:  # noqa: BLE001 - 研究 Agent 不可用时降级
            logger.warning("研究 Agent 初始化失败 error=%s", type(exc).__name__)
    return ResearchService(settings, agent=agent)
