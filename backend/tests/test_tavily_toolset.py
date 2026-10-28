from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.search.source_collector import SourceCollector
from app.search.tavily_tools import build_tavily_toolset, wrap_tool


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "llm_provider": "mock",
        "web_search_enabled": True,
        "web_search_provider": "tavily",
        "tavily_api_key": "tvly-test-key",
        "tavily_proxy_url": "",
        "tavily_trust_env_proxy": False,
    }
    values.update(overrides)
    return Settings(**values)


def make_collector() -> SourceCollector:
    return SourceCollector(
        search_result_max_chars=1000,
        extract_result_max_chars=2000,
        tool_total_max_chars=5000,
    )


def test_toolset_with_country_has_expected_tools_and_presets() -> None:
    suite = build_tavily_toolset(make_settings(), collector=make_collector(), country="china")

    assert [tool.name for tool in suite.tools] == [
        "tavily_search_quick_local",
        "tavily_search_deep_local",
        "tavily_search_quick_global",
        "tavily_search_deep_global",
        "tavily_extract_page",
    ]
    assert suite.has_local_tools is True
    assert suite.prefer_sync is False
    assert suite.presets["tavily_search_quick_local"].max_results == 4
    assert suite.presets["tavily_search_quick_local"].include_raw_content is False
    assert suite.presets["tavily_search_quick_local"].country == "china"
    assert suite.presets["tavily_search_deep_local"].max_results == 5
    assert suite.presets["tavily_search_deep_local"].include_raw_content == "markdown"
    assert suite.presets["tavily_search_deep_global"].country is None
    assert suite.presets["tavily_extract_page"].kind == "extract"


def test_toolset_without_country_only_has_global_tools() -> None:
    suite = build_tavily_toolset(make_settings(), collector=make_collector(), country=None)

    assert [tool.name for tool in suite.tools] == [
        "tavily_search_quick_global",
        "tavily_search_deep_global",
        "tavily_extract_page",
    ]
    assert suite.has_local_tools is False


def test_toolset_uses_sync_path_when_proxy_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(name, "")

    suite = build_tavily_toolset(
        make_settings(tavily_proxy_url="http://127.0.0.1:7897"),
        collector=make_collector(),
    )

    assert suite.prefer_sync is True


def test_toolset_requires_api_key() -> None:
    with pytest.raises(RuntimeError):
        build_tavily_toolset(make_settings(tavily_api_key=""), collector=make_collector())


def test_toolset_requires_enabled_search() -> None:
    with pytest.raises(RuntimeError):
        build_tavily_toolset(
            make_settings(web_search_enabled=False), collector=make_collector()
        )


class FakeInput(BaseModel):
    query: str = ""


class FakeInner:
    args_schema = FakeInput

    def __init__(self, result: dict[str, Any], *, delay: float = 0.0, fail: bool = False) -> None:
        self.result = result
        self.delay = delay
        self.fail = fail
        self.sync_calls = 0
        self.async_calls = 0

    def invoke(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        self.sync_calls += 1
        if self.fail:
            raise ValueError("sync failed")
        time.sleep(self.delay)
        return self.result

    async def ainvoke(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        self.async_calls += 1
        if self.fail:
            raise ValueError("async failed")
        await asyncio.sleep(self.delay)
        return self.result


SEARCH_RESULT = {
    "results": [
        {"title": "T", "url": "https://example.com/a", "content": "content", "score": 1.0}
    ]
}


async def test_wrap_tool_uses_sync_path_when_preferred() -> None:
    inner = FakeInner(SEARCH_RESULT)
    tool = wrap_tool(
        inner,  # type: ignore[arg-type]
        name="fake_search",
        description="fake",
        collector=make_collector(),
        timeout_seconds=1.0,
        prefer_sync=True,
    )

    result = await tool.ainvoke({"query": "x"})

    assert inner.sync_calls == 1
    assert inner.async_calls == 0
    assert result["results"][0]["content"] == "content"


async def test_wrap_tool_uses_async_path_by_default() -> None:
    inner = FakeInner(SEARCH_RESULT)
    tool = wrap_tool(
        inner,  # type: ignore[arg-type]
        name="fake_search",
        description="fake",
        collector=make_collector(),
        timeout_seconds=1.0,
        prefer_sync=False,
    )

    result = await tool.ainvoke({"query": "x"})

    assert inner.sync_calls == 0
    assert inner.async_calls == 1
    assert result["results"][0]["content"] == "content"


async def test_wrap_tool_returns_error_on_timeout() -> None:
    inner = FakeInner(SEARCH_RESULT, delay=0.2)
    tool = wrap_tool(
        inner,  # type: ignore[arg-type]
        name="fake_search",
        description="fake",
        collector=make_collector(),
        timeout_seconds=0.01,
        prefer_sync=False,
    )

    result = await tool.ainvoke({"query": "x"})

    assert result == {"error": "TimeoutError"}


async def test_wrap_tool_returns_error_on_failure() -> None:
    inner = FakeInner(SEARCH_RESULT, fail=True)
    tool = wrap_tool(
        inner,  # type: ignore[arg-type]
        name="fake_search",
        description="fake",
        collector=make_collector(),
        timeout_seconds=1.0,
        prefer_sync=False,
    )

    result = await tool.ainvoke({"query": "x"})

    assert result == {"error": "ValueError"}
