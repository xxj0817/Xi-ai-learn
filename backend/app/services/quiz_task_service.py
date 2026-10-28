"""异步出题任务的状态管理：创建、进度更新、终态落库与恢复。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ResourceNotFound
from app.models.quiz import Quiz, QuizGenerateRequest
from app.models.quiz_task import (
    QuizTask,
    QuizTaskError,
    QuizTaskStage,
    QuizTaskStatus,
    stage_progress,
)
from app.repositories.quiz_task_repository import (
    QuizTaskRecord,
    QuizTaskRepositoryProtocol,
)
from app.utils.id_generator import new_quiz_task_id

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_CHARS = 200
DEFAULT_ERROR_MESSAGE = "AI 出题失败，请稍后重试"
INTERRUPTED_MESSAGE = "服务重启导致任务中断，请重新生成"


class QuizTaskService:
    def __init__(
        self,
        settings: Settings,
        repository: QuizTaskRepositoryProtocol,
    ) -> None:
        self._settings = settings
        self._repository = repository

    async def create(
        self,
        payload: QuizGenerateRequest,
        *,
        user_id: int | None = None,
    ) -> QuizTask:
        task_id = new_quiz_task_id()
        await self._repository.create(
            task_id=task_id,
            user_id=user_id,
            request=payload.model_dump(mode="json"),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=self._settings.quiz_task_retention_hours),
        )
        record = await self._repository.get(task_id)
        if record is None:
            raise ResourceNotFound("生成任务创建失败，请稍后重试")
        return self._to_model(record)

    async def get(
        self, task_id: str, *, user_id: int | None = None
    ) -> QuizTask | None:
        record = await self._repository.get(task_id)
        if record is None:
            return None
        if record.user_id is not None and record.user_id != user_id:
            return None
        return self._to_model(record)

    async def mark_running(self, task_id: str) -> None:
        await self._repository.mark_running(task_id)

    async def report_progress(
        self, task_id: str, stage: QuizTaskStage
    ) -> None:
        # progress 由 stage 推导（见 STAGE_PROGRESS），落库只记录 stage
        await self._repository.set_stage(task_id, stage=stage.value)

    async def mark_succeeded(self, task_id: str, quiz: Quiz) -> None:
        await self._repository.mark_succeeded(
            task_id,
            quiz_id=quiz.quiz_id,
            result=quiz.model_dump(mode="json"),
        )

    async def mark_failed(
        self, task_id: str, *, code: int, message: str
    ) -> None:
        await self._repository.mark_failed(
            task_id,
            code=code,
            message=(message or DEFAULT_ERROR_MESSAGE)[:MAX_ERROR_MESSAGE_CHARS],
        )

    async def recover_interrupted(self) -> int:
        """进程启动时把上次未完成的任务标记为失败，避免前端一直轮询。"""
        try:
            count = await self._repository.fail_stale(message=INTERRUPTED_MESSAGE)
        except Exception as exc:  # noqa: BLE001 - 恢复失败不影响服务启动
            logger.warning("中断任务恢复失败 error=%s", type(exc).__name__)
            return 0
        if count:
            logger.info("已将 %s 个中断的出题任务标记为失败", count)
        return count

    async def purge_expired(self) -> int:
        try:
            count = await self._repository.purge_finished()
        except Exception as exc:  # noqa: BLE001 - 清理失败不影响服务启动
            logger.warning("过期任务清理失败 error=%s", type(exc).__name__)
            return 0
        if count:
            logger.info("已清理 %s 个过期出题任务", count)
        return count

    def _to_model(self, record: QuizTaskRecord) -> QuizTask:
        status = _parse_status(record.status)
        stage = _parse_stage(record.stage)
        quiz = None
        if status is QuizTaskStatus.succeeded and record.result:
            quiz = self._parse_quiz(record.result)
        error = None
        if status is QuizTaskStatus.failed:
            error = QuizTaskError(
                code=record.error_code or 5000,
                message=record.error_message or DEFAULT_ERROR_MESSAGE,
            )
        return QuizTask(
            task_id=record.task_id,
            status=status,
            stage=stage,
            progress=stage_progress(stage),
            quiz_id=record.quiz_id,
            quiz=quiz,
            error=error,
            poll_interval_ms=self._settings.quiz_task_poll_interval_ms,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _parse_quiz(self, result: dict[str, Any]) -> Quiz | None:
        try:
            return Quiz.model_validate(result)
        except Exception as exc:  # noqa: BLE001 - 脏数据不应阻断轮询
            logger.warning("任务结果解析失败 error=%s", type(exc).__name__)
            return None


def _parse_status(value: str) -> QuizTaskStatus:
    try:
        return QuizTaskStatus(value)
    except ValueError:
        return QuizTaskStatus.pending


def _parse_stage(value: str) -> QuizTaskStage:
    try:
        return QuizTaskStage(value)
    except ValueError:
        return QuizTaskStage.queued
