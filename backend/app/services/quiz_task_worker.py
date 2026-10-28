"""异步出题任务的执行器：后台调度、并发控制、超时与失败收敛。"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from app.core.config import Settings
from app.core.exceptions import AppError
from app.models.quiz import QuizGenerateRequest
from app.models.quiz_task import QuizTask, QuizTaskStage
from app.services.quiz_service import QuizService
from app.services.quiz_task_service import QuizTaskService

logger = logging.getLogger(__name__)

TIMEOUT_CODE = 5040
TIMEOUT_MESSAGE = "AI 出题超时，请稍后重试"
UNKNOWN_CODE = 5000
UNKNOWN_MESSAGE = "AI 出题失败，请稍后重试"


class QuizTaskWorker:
    """把出题请求放进后台执行，接口立即返回任务状态。"""

    def __init__(
        self,
        *,
        settings: Settings,
        service: QuizTaskService,
        quiz_service_factory: Callable[[], QuizService],
    ) -> None:
        self._settings = settings
        self._service = service
        self._quiz_service_factory = quiz_service_factory
        self._semaphore = asyncio.Semaphore(settings.quiz_task_max_concurrency)
        self._running: dict[str, asyncio.Task[None]] = {}

    async def submit(
        self,
        payload: QuizGenerateRequest,
        *,
        user_id: int | None = None,
        accept_language: str | None = None,
    ) -> QuizTask:
        self._quiz_service_factory().validate(payload)
        task = await self._service.create(
            payload,
            user_id=user_id,
        )
        self._spawn(task.task_id, payload, user_id, accept_language)
        return task

    async def get(
        self, task_id: str, *, user_id: int | None = None
    ) -> QuizTask | None:
        return await self._service.get(task_id, user_id=user_id)

    async def recover(self) -> None:
        await self._service.recover_interrupted()
        await self._service.purge_expired()

    async def shutdown(self) -> None:
        pending = list(self._running.values())
        self._running.clear()
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    @property
    def active_count(self) -> int:
        return len(self._running)

    def _spawn(
        self,
        task_id: str,
        payload: QuizGenerateRequest,
        user_id: int | None,
        accept_language: str | None,
    ) -> None:
        task = asyncio.create_task(
            self._execute(task_id, payload, user_id, accept_language),
            name=f"quiz-task:{task_id}",
        )
        self._running[task_id] = task
        task.add_done_callback(
            lambda _finished, tid=task_id: self._running.pop(tid, None)
        )

    async def _execute(
        self,
        task_id: str,
        payload: QuizGenerateRequest,
        user_id: int | None,
        accept_language: str | None,
    ) -> None:
        try:
            async with self._semaphore:
                await self._service.mark_running(task_id)
                quiz = await asyncio.wait_for(
                    self._quiz_service_factory().generate(
                        payload,
                        user_id=user_id,
                        accept_language=accept_language,
                        on_progress=lambda stage: self._report(task_id, stage),
                    ),
                    timeout=self._settings.quiz_task_timeout_seconds,
                )
                await self._service.mark_succeeded(task_id, quiz)
        except asyncio.CancelledError:
            logger.info("出题任务被取消 task_id=%s", task_id)
            raise
        except asyncio.TimeoutError:
            logger.warning("出题任务超时 task_id=%s", task_id)
            await self._safe_fail(task_id, TIMEOUT_CODE, TIMEOUT_MESSAGE)
        except AppError as exc:
            logger.info("出题任务失败 task_id=%s code=%s", task_id, exc.code)
            await self._safe_fail(task_id, exc.code, exc.message)
        except Exception as exc:  # noqa: BLE001 - 后台任务必须收敛，不能吞掉进程
            logger.exception(
                "出题任务异常 task_id=%s error=%s", task_id, type(exc).__name__
            )
            await self._safe_fail(task_id, UNKNOWN_CODE, UNKNOWN_MESSAGE)

    async def _report(self, task_id: str, stage: QuizTaskStage) -> None:
        try:
            await self._service.report_progress(task_id, stage)
        except Exception as exc:  # noqa: BLE001 - 进度更新失败不影响出题
            logger.debug(
                "出题任务进度更新失败 task_id=%s error=%s",
                task_id,
                type(exc).__name__,
            )

    async def _safe_fail(self, task_id: str, code: int, message: str) -> None:
        try:
            await self._service.mark_failed(task_id, code=code, message=message)
        except Exception as exc:  # noqa: BLE001 - 失败状态兜底写库
            logger.warning(
                "出题任务失败状态写入失败 task_id=%s error=%s",
                task_id,
                type(exc).__name__,
            )
