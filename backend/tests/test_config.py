from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_use_mock_provider_and_deepseek_flash() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "mock"
    assert settings.deepseek_model == "deepseek-flash"
    assert settings.deepseek_thinking_enabled is False
    assert settings.quiz_default_question_count == 5


def test_deepseek_provider_requires_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="deepseek", deepseek_api_key="")


def test_invalid_question_count_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, quiz_min_question_count=6, quiz_max_question_count=4)


def test_web_search_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.web_search_enabled is True
    assert settings.web_search_provider == "tavily"
    assert settings.tavily_api_key == ""
    assert settings.tavily_quick_max_results == 4
    assert settings.tavily_deep_max_results == 5
    assert settings.tavily_deep_search_depth == "advanced"
    assert settings.tavily_deep_include_raw_content == "markdown"
    assert settings.tavily_extract_chunks_per_source == 3
    assert settings.web_search_max_sources == 6
    assert settings.user_source_min_chars == 800
    assert settings.web_search_cache_ttl_seconds == 1800


def test_missing_tavily_key_still_builds_settings() -> None:
    settings = Settings(_env_file=None, llm_provider="mock", tavily_api_key="")

    assert settings.tavily_api_key == ""
    assert settings.web_search_enabled is True


def test_web_search_can_be_disabled() -> None:
    settings = Settings(_env_file=None, web_search_enabled=False, web_search_provider="none")

    assert settings.web_search_enabled is False
    assert settings.web_search_provider == "none"


def test_invalid_tavily_preset_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, tavily_quick_max_results=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, tavily_extract_chunks_per_source=6)


def test_invalid_source_budget_order_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            source_snippet_max_chars=2000,
            source_total_max_chars=1000,
        )

