"""出题服务：输入校验 → LLM 生成 → 结构校验与重试。"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.exceptions import AIProviderError, AppError, InvalidInput, QuizFormatError
from app.llm.base import LearningAIProvider
from app.models.quiz import Quiz, QuizGenerateRequest
from app.services.quiz_normalizer import normalize_quiz
from app.utils.content_filter import ensure_safe
from app.utils.id_generator import new_quiz_id
from app.utils.text_cleaner import clean_input

logger = logging.getLogger(__name__)


class QuizService:
    def __init__(self, settings: Settings, provider: LearningAIProvider) -> None:
        self._settings = settings
        self._provider = provider

    async def generate(self, request: QuizGenerateRequest) -> Quiz:
        user_input = clean_input(
            request.user_input,
            min_chars=self._settings.quiz_min_input_chars,
            max_chars=self._settings.quiz_max_input_chars,
        )
        ensure_safe(user_input)
        self._validate_question_count(request.question_count)

        quiz_id = new_quiz_id()
        last_error: Exception | None = None

        for attempt in range(self._settings.llm_max_attempts):
            strict = attempt > 0
            try:
                draft = await self._provider.generate_quiz(
                    topic=user_input,
                    question_count=request.question_count,
                    difficulty=request.difficulty,
                    strict=strict,
                )
                return normalize_quiz(
                    draft,
                    quiz_id=quiz_id,
                    user_input=user_input,
                    expected_count=request.question_count,
                )
            except AppError:
                raise
            except QuizFormatError as exc:
                last_error = exc
                logger.warning("题库结构校验失败 attempt=%s reason=%s", attempt + 1, exc)
            except Exception as exc:  # noqa: BLE001 - 统一收敛为可重试错误
                last_error = exc
                logger.warning("出题调用失败 attempt=%s error=%s", attempt + 1, type(exc).__name__)

        raise AIProviderError() from last_error

    def _validate_question_count(self, count: int) -> None:
        if not self._settings.quiz_min_question_count <= count <= self._settings.quiz_max_question_count:
            raise InvalidInput(
                f"题目数量需要在 {self._settings.quiz_min_question_count} 到 "
                f"{self._settings.quiz_max_question_count} 之间"
            )
