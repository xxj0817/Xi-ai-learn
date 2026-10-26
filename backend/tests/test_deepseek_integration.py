from __future__ import annotations

import asyncio
import os

import pytest

from app.core.config import Settings
from app.llm.deepseek_provider import DeepSeekProvider
from app.services.quiz_normalizer import normalize_quiz
from app.utils.content_filter import ensure_safe
from app.utils.text_cleaner import clean_input

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("DEEPSEEK_API_KEY"),
        reason="需要真实 DEEPSEEK_API_KEY 才会执行",
    ),
]


def test_deepseek_generates_a_valid_quiz() -> None:
    settings = Settings(_env_file=None, llm_provider="deepseek")
    provider = DeepSeekProvider(settings)
    user_input = clean_input("RAG 和传统搜索有什么区别")
    ensure_safe(user_input)

    draft = asyncio.run(
        provider.generate_quiz(
            topic=user_input,
            question_count=5,
            difficulty="mixed",
        )
    )

    quiz = normalize_quiz(
        draft,
        quiz_id="quiz_integration",
        user_input=user_input,
        expected_count=5,
    )

    assert len(quiz.questions) == 5
    assert all(question.explanation for question in quiz.questions)
