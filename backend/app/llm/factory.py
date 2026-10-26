"""Provider 工厂。"""

from __future__ import annotations

from app.core.config import Settings
from app.llm.base import LearningAIProvider


def build_provider(settings: Settings) -> LearningAIProvider:
    if settings.llm_provider == "deepseek":
        from app.llm.deepseek_provider import DeepSeekProvider

        return DeepSeekProvider(settings)
    from app.llm.mock_provider import MockProvider

    return MockProvider()
