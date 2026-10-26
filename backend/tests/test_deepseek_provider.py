from __future__ import annotations

import asyncio

import pytest
from langchain_core.runnables import RunnableLambda

from app.core.config import Settings
from app.core.exceptions import AIProviderError
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.schemas import QuizDraft, ReportDraft


def deepseek_settings() -> Settings:
    return Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="sk-test")


def test_model_uses_deepseek_flash_with_thinking_disabled() -> None:
    provider = DeepSeekProvider(deepseek_settings())

    model = provider._build_model(temperature=0.4, max_tokens=1200)

    assert model.model_name == "deepseek-flash"
    assert model.extra_body == {"thinking": {"type": "disabled"}}
    assert str(model.openai_api_base) == "https://api.deepseek.com"
    assert model.request_timeout == 30.0


def test_thinking_mode_can_be_enabled_by_settings() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="deepseek",
        deepseek_api_key="sk-test",
        deepseek_thinking_enabled=True,
    )

    model = DeepSeekProvider(settings)._build_model(temperature=0.4, max_tokens=1200)

    assert model.extra_body == {"thinking": {"type": "enabled"}}


class FakeModel:
    def __init__(self, outcomes: dict[str, object]) -> None:
        self.outcomes = outcomes
        self.methods: list[str] = []

    def with_structured_output(self, schema, method: str, include_raw: bool):
        self.methods.append(method)
        outcome = self.outcomes[method]
        if isinstance(outcome, Exception):
            def raise_error(_: object) -> object:
                raise outcome

            return RunnableLambda(raise_error)
        return RunnableLambda(lambda _: outcome)


def test_function_calling_failure_falls_back_to_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    draft = QuizDraft(title="RAG 闯关", questions=[])
    fake_model = FakeModel(
        {
            "function_calling": RuntimeError("tool calls unsupported"),
            "json_mode": {"parsed": draft, "raw": None},
        }
    )
    provider = DeepSeekProvider(deepseek_settings())
    monkeypatch.setattr(provider, "_build_model", lambda **_: fake_model)

    result = asyncio.run(
        provider.generate_quiz(topic="RAG", question_count=5, difficulty="mixed")
    )

    assert result is draft
    assert fake_model.methods == ["function_calling", "json_mode"]


def test_both_structured_output_methods_failing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = FakeModel(
        {
            "function_calling": RuntimeError("tool calls unsupported"),
            "json_mode": {"parsed": None, "parsing_error": "bad json"},
        }
    )
    provider = DeepSeekProvider(deepseek_settings())
    monkeypatch.setattr(provider, "_build_model", lambda **_: fake_model)

    with pytest.raises(AIProviderError):
        asyncio.run(provider.generate_report(topic="RAG", quiz_summary="s", question_results=[], stats={}))


def test_report_uses_parsed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    draft = ReportDraft(three_line_summary=["a", "b", "c"], advice=["x"], share_quote="q")
    fake_model = FakeModel(
        {
            "function_calling": {"parsed": draft, "raw": None},
            "json_mode": RuntimeError("should not be called"),
        }
    )
    provider = DeepSeekProvider(deepseek_settings())
    monkeypatch.setattr(provider, "_build_model", lambda **_: fake_model)

    result = asyncio.run(
        provider.generate_report(topic="RAG", quiz_summary="s", question_results=[], stats={})
    )

    assert result is draft
    assert fake_model.methods == ["function_calling"]
