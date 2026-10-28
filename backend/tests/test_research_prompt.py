from __future__ import annotations

from datetime import date

from app.prompts.research_prompt import (
    RESEARCH_PROMPT_VERSION,
    build_research_system_prompt,
    build_research_user_message,
)


def test_research_prompt_version() -> None:
    assert RESEARCH_PROMPT_VERSION == "research_prompt_v1"


def test_system_prompt_contains_tool_policy_and_injection_guard() -> None:
    prompt = build_research_system_prompt(
        today=date(2026, 10, 28),
        region_label="中国",
        locale="zh-CN",
        has_local_tools=True,
    )

    assert "2026-10-28" in prompt
    assert "中国" in prompt
    assert "tavily_extract_page" in prompt
    assert "quick" in prompt
    assert "deep" in prompt
    assert "不可信数据" in prompt
    assert "不得执行" in prompt
    assert "topic" in prompt
    assert "used_urls" in prompt
    assert "local" in prompt
    assert "global" in prompt


def test_system_prompt_without_local_tools() -> None:
    prompt = build_research_system_prompt(
        today=date(2026, 10, 28),
        region_label="全球",
        locale="en-US",
        has_local_tools=False,
    )

    assert "没有 local 工具" in prompt


def test_user_message_embeds_input_urls_and_material() -> None:
    message = build_research_user_message(
        user_input="https://example.com/a 这篇讲什么",
        urls=["https://example.com/a"],
        source_text="用户粘贴的资料",
        region_label="中国",
        today=date(2026, 10, 28),
    )

    assert "https://example.com/a" in message
    assert "这篇讲什么" in message
    assert "用户粘贴的资料" in message
    assert "2026-10-28" in message
