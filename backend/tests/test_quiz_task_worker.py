from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.core.exceptions import AIProviderError
from app.models.quiz import QuizGenerateRequest
from app.models.quiz_task import QuizTaskStage, QuizTaskStatus
from app.repositories.quiz_task_repository import InMemoryQuizTaskRepository
from app.services.quiz_service import QuizService
from app.services.quiz_task_service import QuizTaskService
from app.services.quiz_task_worker import QuizTaskWorker
from tests.conftest import FakeProvider


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
        "llm_max_attempts": 2,
        "quiz_task_max_concurrency": 2,
        "quiz_task_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return Settings(**values)


class RecordingRepository(InMemoryQuizTaskRepository):
    def __init__(self) -> None:
        super().__init__()
        self.stages: list[str] = []

    async def set_stage(self, task_id: str, *, stage: str) -> None:
        self.stages.append(stage)
        await super().set_stage(task_id, stage=stage)


class SlowProvider(FakeProvider):
    async def generate_quiz(self, **kwargs: Any):  # type: ignore[override]
        await asyncio.sleep(0.3)
        return await super().generate_quiz(**kwargs)


def build_worker(
    provider: FakeProvider | None = None,
    *,
    settings: Settings | None = None,
) -> tuple[QuizTaskWorker, QuizTaskService, RecordingRepository]:
    settings = settings or make_settings()
    repository = RecordingRepository()
    service = QuizTaskService(settings, repository)
    worker = QuizTaskWorker(
        settings=settings,
        service=service,
        quiz_service_factory=lambda: QuizService(settings, provider or FakeProvider()),
    )
    return worker, service, repository


async def wait_terminal(
    worker: QuizTaskWorker, task_id: str, timeout: float = 5.0
):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    task = None
    while loop.time() < deadline:
        task = await worker.get(task_id)
        if task is not None and task.is_terminal:
            return task
        await asyncio.sleep(0.01)
    raise AssertionError(f"任务未在预期时间内结束: {task}")


async def test_submit_returns_pending_task_immediately() -> None:
    worker, _service, _repo = build_worker()

    task = await worker.submit(QuizGenerateRequest(user_input="Harness Engineering"))

    assert task.status is QuizTaskStatus.pending
    assert task.stage is QuizTaskStage.queued
    assert task.progress == 0
    assert task.quiz is None
    assert worker.active_count == 1
    await worker.shutdown()


async def test_worker_completes_task_with_quiz_and_progress() -> None:
    provider = FakeProvider()
    worker, _service, repository = build_worker(provider)

    task = await worker.submit(QuizGenerateRequest(user_input="RAG 是什么"))
    final = await wait_terminal(worker, task.task_id)

    assert final.status is QuizTaskStatus.succeeded
    assert final.stage is QuizTaskStage.completed
    assert final.progress == 100
    assert final.quiz is not None
    assert len(final.quiz.questions) == 5
    assert final.quiz_id == final.quiz.quiz_id
    assert repository.stages == [
        "generating",
        "validating",
        "saving",
        "completed",
    ]
    assert provider.quiz_calls[0]["question_count"] == 5
    await worker.shutdown()


async def test_worker_marks_app_error_as_failed() -> None:
    worker, _service, _repo = build_worker(
        FakeProvider(quiz_error=AIProviderError("模型服务不可用"))
    )

    task = await worker.submit(QuizGenerateRequest(user_input="Harness Engineering"))
    final = await wait_terminal(worker, task.task_id)

    assert final.status is QuizTaskStatus.failed
    assert final.stage is QuizTaskStage.failed
    assert final.error is not None
    assert final.error.code == 4002
    assert final.error.message == "模型服务不可用"
    assert final.quiz is None
    await worker.shutdown()


async def test_worker_marks_timeout_as_failed() -> None:
    settings = make_settings(quiz_task_timeout_seconds=0.05)
    worker, _service, _repo = build_worker(SlowProvider(), settings=settings)

    task = await worker.submit(QuizGenerateRequest(user_input="Harness Engineering"))
    final = await wait_terminal(worker, task.task_id)

    assert final.status is QuizTaskStatus.failed
    assert final.error is not None
    assert final.error.code == 5040
    assert "超时" in final.error.message
    await worker.shutdown()


async def test_task_is_visible_only_to_its_owner() -> None:
    worker, _service, _repo = build_worker()

    owned = await worker.submit(QuizGenerateRequest(user_input="RAG"), user_id=7)
    anonymous = await worker.submit(QuizGenerateRequest(user_input="RAG"))

    assert await worker.get(owned.task_id, user_id=7) is not None
    assert await worker.get(owned.task_id, user_id=8) is None
    # 匿名任务由不可猜测的 task_id 保护，登录后仍可继续轮询
    assert await worker.get(anonymous.task_id, user_id=8) is not None
    await worker.shutdown()


async def test_invalid_request_is_rejected_before_task_creation() -> None:
    worker, _service, repository = build_worker()

    try:
        await worker.submit(
            QuizGenerateRequest(user_input="RAG", question_count=2)
        )
    except Exception as exc:  # noqa: BLE001 - 断言异常类型
        assert type(exc).__name__ == "InvalidInput"
    else:
        raise AssertionError("越界的题目数量应当被拒绝")

    assert worker.active_count == 0
    assert repository.stages == []
    await worker.shutdown()


async def test_interrupted_tasks_are_failed_on_startup() -> None:
    settings = make_settings()
    repository = InMemoryQuizTaskRepository()
    service = QuizTaskService(settings, repository)
    await repository.create(
        task_id="task_stale",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    assert await service.recover_interrupted() == 1

    task = await service.get("task_stale")
    assert task is not None
    assert task.status is QuizTaskStatus.failed
    assert task.error is not None
    assert task.error.code == 5001
