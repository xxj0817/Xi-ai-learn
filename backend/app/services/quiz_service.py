"""出题服务：输入校验 → 研究 → LLM 生成 → 结构/引证校验与重试。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.exceptions import AIProviderError, AppError, InvalidInput, QuizFormatError
from app.llm.base import LearningAIProvider
from app.models.quiz import (
    GroundingStatus,
    Quiz,
    QuizGenerateRequest,
    QuizGrounding,
    QuizSource,
    SourceOrigin,
)
from app.models.quiz_task import QuizTaskStage
from app.repositories.quiz_repository import QuizRepositoryProtocol
from app.services.quiz_normalizer import normalize_quiz
from app.utils.content_filter import ensure_safe
from app.utils.id_generator import new_quiz_id
from app.utils.text_cleaner import clean_input

if TYPE_CHECKING:
    from app.services.research_service import ResearchResult, ResearchService

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[QuizTaskStage], Awaitable[None]]


class QuizService:
    def __init__(
        self,
        settings: Settings,
        provider: LearningAIProvider,
        quiz_repository: QuizRepositoryProtocol | None = None,
        research_service: "ResearchService | None" = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._quiz_repository = quiz_repository
        self._research_service = research_service

    def validate(self, request: QuizGenerateRequest) -> str:
        """同步校验请求，异步任务在创建阶段即可返回明确的 400。"""
        user_input = clean_input(
            request.user_input,
            min_chars=self._settings.quiz_min_input_chars,
            max_chars=self._settings.quiz_max_input_chars,
        )
        ensure_safe(user_input)
        self._validate_question_count(request.question_count)
        return user_input

    async def generate(
        self,
        request: QuizGenerateRequest,
        *,
        user_id: int | None = None,
        accept_language: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Quiz:
        user_input = self.validate(request)

        research: ResearchResult | None = None
        if self._research_service is not None:
            await self._emit(on_progress, QuizTaskStage.researching)
            try:
                research = await self._research_service.gather(
                    user_input=user_input,
                    source_text=request.source_text,
                    source_urls=request.source_urls,
                    region=request.region,
                    locale=request.locale,
                    accept_language=accept_language,
                )
            except Exception as exc:  # noqa: BLE001 - 研究失败不阻断出题
                logger.warning("研究服务失败 error=%s", type(exc).__name__)

        await self._emit(on_progress, QuizTaskStage.generating)

        sources: list[QuizSource] = research.sources if research is not None else []
        valid_source_ids = {source.id for source in sources}
        topic = research.topic if research is not None and research.topic else user_input

        quiz_id = new_quiz_id()
        last_error: Exception | None = None
        partial_quiz: Quiz | None = None

        for attempt in range(self._settings.llm_max_attempts):
            strict = attempt > 0
            try:
                draft = await self._provider.generate_quiz(
                    topic=topic,
                    question_count=request.question_count,
                    difficulty=request.difficulty,
                    sources=sources,
                    strict=strict,
                )
                quiz = normalize_quiz(
                    draft,
                    quiz_id=quiz_id,
                    user_input=user_input,
                    expected_count=request.question_count,
                    valid_source_ids=valid_source_ids,
                )
            except AppError:
                raise
            except QuizFormatError as exc:
                last_error = exc
                logger.warning("题库结构校验失败 attempt=%s reason=%s", attempt + 1, exc)
                continue
            except Exception as exc:  # noqa: BLE001 - 统一收敛为可重试错误
                last_error = exc
                logger.warning("出题调用失败 attempt=%s error=%s", attempt + 1, type(exc).__name__)
                continue

            missing_citations = bool(sources) and any(
                not question.citations for question in quiz.questions
            )
            await self._emit(on_progress, QuizTaskStage.validating)
            if missing_citations and attempt + 1 < self._settings.llm_max_attempts:
                partial_quiz = quiz
                last_error = QuizFormatError("存在缺少有效引证的题目")
                logger.warning("题库引证校验失败 attempt=%s，准备重试", attempt + 1)
                continue

            if sources:
                status = (
                    GroundingStatus.partial
                    if missing_citations
                    else GroundingStatus.grounded
                )
            else:
                status = GroundingStatus.model_only

            return await self._complete(
                quiz, sources, research, status, user_id, on_progress
            )

        if partial_quiz is not None:
            logger.warning("引证重试未得到有效题库，返回首次可用题目并标记部分核实")
            return await self._complete(
                partial_quiz,
                sources,
                research,
                GroundingStatus.partial,
                user_id,
                on_progress,
            )

        raise AIProviderError() from last_error

    async def _complete(
        self,
        quiz: Quiz,
        sources: list[QuizSource],
        research: ResearchResult | None,
        status: GroundingStatus,
        user_id: int | None,
        on_progress: ProgressCallback | None = None,
    ) -> Quiz:
        await self._emit(on_progress, QuizTaskStage.saving)
        quiz.sources = list(sources)
        quiz.source_type = self._source_type(sources)
        quiz.grounding = QuizGrounding(
            status=status,
            provider=research.provider if research is not None else "none",
            searched_at=research.searched_at if research is not None else None,
            evidence_chars=research.evidence_chars if research is not None else 0,
        )
        await self._persist(quiz, user_id)
        await self._emit(on_progress, QuizTaskStage.completed)
        return quiz

    async def _persist(self, quiz: Quiz, user_id: int | None) -> None:
        if user_id is None or self._quiz_repository is None:
            return
        try:
            await self._quiz_repository.save_quiz(
                quiz_id=quiz.quiz_id,
                user_id=user_id,
                title=quiz.title,
                summary=quiz.summary,
                user_input=quiz.user_input,
                questions=[question.model_dump(mode="json") for question in quiz.questions],
            )
            save_grounding = getattr(self._quiz_repository, "save_grounding", None)
            if save_grounding is not None:
                await save_grounding(
                    quiz_id=quiz.quiz_id,
                    user_id=user_id,
                    sources=[source.model_dump(mode="json") for source in quiz.sources],
                    grounding=quiz.grounding.model_dump(mode="json"),
                )
        except Exception as exc:  # noqa: BLE001 - 持久化失败不应影响出题结果
            logger.warning("题库落库失败 quiz_id=%s error=%s", quiz.quiz_id, type(exc).__name__)

    async def _emit(
        self,
        callback: ProgressCallback | None,
        stage: QuizTaskStage,
    ) -> None:
        if callback is None:
            return
        try:
            await callback(stage)
        except Exception as exc:  # noqa: BLE001 - 进度上报失败不影响出题
            logger.debug("出题进度上报失败 stage=%s error=%s", stage, type(exc).__name__)

    def _source_type(self, sources: list[QuizSource]) -> str:
        has_user = any(source.origin == SourceOrigin.user for source in sources)
        has_web = any(source.origin == SourceOrigin.web for source in sources)
        if has_user and has_web:
            return "mixed"
        if has_user:
            return "user"
        if has_web:
            return "web"
        return "text"

    def _validate_question_count(self, count: int) -> None:
        if not self._settings.quiz_min_question_count <= count <= self._settings.quiz_max_question_count:
            raise InvalidInput(
                f"题目数量需要在 {self._settings.quiz_min_question_count} 到 "
                f"{self._settings.quiz_max_question_count} 之间"
            )
