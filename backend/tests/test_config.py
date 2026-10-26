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
