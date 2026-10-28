from __future__ import annotations

import asyncio

import pytest

from app.agents import research_agent as module
from app.agents.research_agent import ResearchAgent, ResearchAgentUnavailable
from app.core.config import Settings
from app.llm.schemas import ResearchBrief
from app.services.region_resolver import RegionContext


def deepseek_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "deepseek",
        "deepseek_api_key": "sk-test",
    }
    values.update(overrides)
    return Settings(**values)


def test_agent_requires_deepseek_provider() -> None:
    with pytest.raises(ResearchAgentUnavailable):
        ResearchAgent(Settings(_env_file=None, llm_provider="mock"))


def test_agent_builds_tools_prompt_and_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            captured["payload"] = payload
            captured["config"] = config
            return {
                "structured_response": ResearchBrief(
                    topic="Harness Engineering",
                    used_urls=["https://example.com/a"],
                )
            }

    def fake_create_agent(model, tools, **kwargs):
        captured["model"] = model
        captured["tools"] = tools
        captured["kwargs"] = kwargs
        return FakeAgent()

    monkeypatch.setattr(module, "build_deepseek_chat_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "create_agent", fake_create_agent)

    agent = ResearchAgent(deepseek_settings())
    brief = asyncio.run(
        agent.run(
            tools=[],
            user_input="Harness Engineering",
            urls=[],
            source_text="",
            region=RegionContext(locale="zh-CN", country="china", label="中国"),
        )
    )

    assert brief.topic == "Harness Engineering"
    assert captured["tools"] == []
    kwargs = captured["kwargs"]
    assert kwargs["response_format"] is ResearchBrief
    assert len(kwargs["middleware"]) == 2
    assert "Harness Engineering" in kwargs["system_prompt"] or "研究助手" in kwargs["system_prompt"]
    assert captured["config"] == {"recursion_limit": 30}


def test_agent_accepts_dict_structured_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"structured_response": {"topic": "T", "used_urls": ["u"]}}

    monkeypatch.setattr(module, "build_deepseek_chat_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "create_agent", lambda *args, **kwargs: FakeAgent())

    brief = asyncio.run(
        ResearchAgent(deepseek_settings()).run(
            tools=[],
            user_input="T",
            urls=[],
            source_text="",
            region=RegionContext(locale="en-US", country=None, label="全球"),
        )
    )

    assert brief.topic == "T"
    assert brief.used_urls == ["u"]


def test_agent_returns_empty_brief_when_structured_response_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAgent:
        async def ainvoke(self, payload, config=None):
            return {"messages": []}

    monkeypatch.setattr(module, "build_deepseek_chat_model", lambda *args, **kwargs: object())
    monkeypatch.setattr(module, "create_agent", lambda *args, **kwargs: FakeAgent())

    brief = asyncio.run(
        ResearchAgent(deepseek_settings()).run(
            tools=[],
            user_input="T",
            urls=[],
            source_text="",
            region=RegionContext(locale="en-US", country=None, label="全球"),
        )
    )

    assert brief.topic == ""
