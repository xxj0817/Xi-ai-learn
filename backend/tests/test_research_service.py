from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.llm.schemas import ResearchBrief
from app.models.quiz import SourceOrigin
from app.search.cache import TTLCache
from app.services.research_service import ResearchService


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "deepseek",
        "deepseek_api_key": "sk-test",
        "tavily_api_key": "tvly-test",
        "web_search_enabled": True,
        "web_search_provider": "tavily",
    }
    values.update(overrides)
    return Settings(**values)


class FakeTool:
    def __init__(self, name: str, collector, results: list[dict]) -> None:
        self.name = name
        self._collector = collector
        self._results = results
        self.calls: list[dict] = []

    async def ainvoke(self, payload: dict):
        self.calls.append(payload)
        for result in self._results:
            self._collector.record(self.name, result)
        return {"results": []}


class FakeSuite:
    def __init__(self, tools: list[FakeTool]) -> None:
        self.tools = tools


class FakeBuilder:
    def __init__(
        self,
        *,
        search_results: list[dict] | None = None,
        extract_results: list[dict] | None = None,
        fail: bool = False,
    ) -> None:
        self.search_results = search_results or []
        self.extract_results = extract_results or []
        self.fail = fail
        self.calls = 0
        self.last_tools: list[FakeTool] = []

    def __call__(self, settings: Settings, *, collector, country):
        self.calls += 1
        if self.fail:
            raise RuntimeError("no toolset")
        tools = [
            FakeTool("tavily_extract_page", collector, self.extract_results),
            FakeTool("tavily_search_quick_global", collector, self.search_results),
            FakeTool("tavily_search_quick_local", collector, self.search_results),
            FakeTool("tavily_search_deep_global", collector, self.search_results),
        ]
        self.last_tools = tools
        return FakeSuite(tools)


class FakeAgent:
    def __init__(
        self,
        *,
        brief: ResearchBrief | None = None,
        error: Exception | None = None,
        tool_name: str = "tavily_search_quick_global",
    ) -> None:
        self.brief = brief or ResearchBrief()
        self.error = error
        self.tool_name = tool_name
        self.calls: list[dict] = []

    async def run(self, *, tools, user_input, urls, source_text, region):
        self.calls.append(
            {
                "user_input": user_input,
                "urls": urls,
                "source_text": source_text,
                "region": region,
            }
        )
        if self.error is not None:
            raise self.error
        tool = next((item for item in tools if item.name == self.tool_name), None)
        if tool is not None:
            await tool.ainvoke({"query": user_input})
        return self.brief


def service(
    *,
    agent=None,
    builder=None,
    cache: TTLCache | None = None,
) -> ResearchService:
    return ResearchService(
        make_settings(),
        agent=agent,
        cache=cache or TTLCache(60),
        toolset_builder=builder or FakeBuilder(),
        now=lambda: datetime(2026, 10, 28, tzinfo=timezone.utc),
    )


WEB_RESULT = {
    "results": [
        {
            "title": "Harness Engineering",
            "url": "https://example.com/harness",
            "content": "Harness Engineering 是 AI Agent 工程实践。" * 10,
            "score": 1.0,
        }
    ]
}


def test_sufficient_source_text_skips_all_tools() -> None:
    builder = FakeBuilder(fail=True)

    result = asyncio.run(
        service(builder=builder).gather(
            user_input="Harness Engineering",
            source_text="用户资料" * 300,
        )
    )

    assert result.mode == "user_only"
    assert result.provider == "user"
    assert len(result.sources) == 1
    assert result.sources[0].origin == SourceOrigin.user
    assert builder.calls == 0


def test_user_urls_are_pre_extracted_before_agent() -> None:
    builder = FakeBuilder(
        extract_results=[
            {
                "results": [
                    {
                        "url": "https://example.com/page",
                        "raw_content": "# 页面主题\n" + "正文" * 500,
                    }
                ]
            }
        ]
    )

    result = asyncio.run(
        service(builder=builder).gather(
            user_input="https://example.com/page 讲了什么",
            source_urls=[],
        )
    )

    assert result.mode == "user_only"
    assert result.provider == "user"
    assert len(result.sources) == 1
    assert result.sources[0].origin == SourceOrigin.user
    assert builder.last_tools[0].calls


def test_agent_sources_use_brief_topic_and_used_urls() -> None:
    builder = FakeBuilder(
        search_results=[
            WEB_RESULT,
            {
                "results": [
                    {
                        "title": "其它",
                        "url": "https://example.com/other",
                        "content": "其它内容",
                        "score": 0.5,
                    }
                ]
            },
        ]
    )
    agent = FakeAgent(
        brief=ResearchBrief(
            topic="Harness Engineering",
            used_urls=["https://example.com/harness"],
        )
    )

    result = asyncio.run(
        service(agent=agent, builder=builder).gather(user_input="Harness Engineering")
    )

    assert result.mode == "agent"
    assert result.topic == "Harness Engineering"
    assert result.provider == "tavily"
    assert [source.url for source in result.sources] == ["https://example.com/harness"]
    assert result.searched_at is not None
    assert result.evidence_chars > 0


def test_agent_timeout_falls_back_to_direct_quick_search() -> None:
    builder = FakeBuilder(search_results=[WEB_RESULT])
    agent = FakeAgent(error=asyncio.TimeoutError())

    result = asyncio.run(
        service(agent=agent, builder=builder).gather(user_input="Harness Engineering")
    )

    assert result.mode == "fallback"
    assert result.provider == "tavily"
    assert len(result.sources) == 1


def test_no_sources_returns_none_mode() -> None:
    result = asyncio.run(
        service(agent=FakeAgent(), builder=FakeBuilder()).gather(user_input="未知主题")
    )

    assert result.mode == "none"
    assert result.provider == "none"
    assert result.sources == []


def test_cache_hit_skips_agent_and_tools() -> None:
    cache: TTLCache = TTLCache(60)
    builder = FakeBuilder(search_results=[WEB_RESULT])
    agent = FakeAgent(brief=ResearchBrief(topic="T", used_urls=["https://example.com/harness"]))
    first_service = service(agent=agent, builder=builder, cache=cache)
    first = asyncio.run(first_service.gather(user_input="T"))

    failing_builder = FakeBuilder(fail=True)
    second_service = service(agent=None, builder=failing_builder, cache=cache)
    second = asyncio.run(second_service.gather(user_input="T"))

    assert first.mode == "agent"
    assert second.mode == "cache"
    assert second.topic == first.topic
    assert len(second.sources) == len(first.sources)
    assert failing_builder.calls == 0


def test_different_source_text_does_not_share_cache() -> None:
    cache: TTLCache = TTLCache(60)
    builder = FakeBuilder(search_results=[WEB_RESULT])
    agent = FakeAgent(brief=ResearchBrief(topic="T", used_urls=["https://example.com/harness"]))
    research = service(agent=agent, builder=builder, cache=cache)

    asyncio.run(research.gather(user_input="T", source_text="第一份资料"))
    asyncio.run(research.gather(user_input="T", source_text="第二份资料"))

    assert builder.calls == 2


def test_missing_tavily_key_skips_tools() -> None:
    builder = FakeBuilder(fail=True)
    research = ResearchService(
        make_settings(tavily_api_key=""),
        agent=None,
        cache=TTLCache(60),
        toolset_builder=builder,
    )

    result = asyncio.run(research.gather(user_input="Harness Engineering"))

    assert result.mode == "none"
    assert builder.calls == 0


def test_failed_toolset_degrades_to_user_sources() -> None:
    research = ResearchService(
        make_settings(),
        agent=FakeAgent(),
        cache=TTLCache(60),
        toolset_builder=FakeBuilder(fail=True),
    )

    result = asyncio.run(
        research.gather(user_input="T", source_text="很短的资料")
    )

    assert result.mode == "user_only"
    assert result.provider == "user"
    assert len(result.sources) == 1


def test_mock_model_still_extracts_user_urls_but_skips_agent() -> None:
    builder = FakeBuilder(
        extract_results=[
            {
                "results": [
                    {
                        "url": "https://example.com/page",
                        "raw_content": "# 页面主题\n" + "正文" * 500,
                    }
                ]
            }
        ]
    )
    research = ResearchService(
        make_settings(llm_provider="mock", deepseek_api_key=""),
        agent=None,
        cache=TTLCache(60),
        toolset_builder=builder,
    )

    result = asyncio.run(research.gather(user_input="https://example.com/page"))

    assert result.mode == "user_only"
    assert result.provider == "user"
    assert builder.calls == 1


def test_user_sources_and_web_sources_produce_mixed_provider() -> None:
    builder = FakeBuilder(search_results=[WEB_RESULT])
    agent = FakeAgent(
        brief=ResearchBrief(topic="T", used_urls=["https://example.com/harness"])
    )

    result = asyncio.run(
        service(agent=agent, builder=builder).gather(
            user_input="T",
            source_text="一小段用户资料",
        )
    )

    assert result.mode == "agent"
    assert result.provider == "mixed"
    assert {source.origin for source in result.sources} == {
        SourceOrigin.user,
        SourceOrigin.web,
    }
