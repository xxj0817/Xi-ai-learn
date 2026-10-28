from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.db import Database
from app.repositories.quiz_task_repository import QuizTaskRepository

pytestmark = pytest.mark.integration


def expires_in(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


async def test_quiz_task_roundtrip(mysql_db: Database) -> None:
    repository = QuizTaskRepository(mysql_db)

    await repository.create(
        task_id="task_roundtrip",
        user_id=None,
        request={"user_input": "Harness Engineering", "question_count": 5},
        expires_at=expires_in(),
    )
    record = await repository.get("task_roundtrip")
    assert record is not None
    assert record.status == "pending"
    assert record.stage == "queued"
    assert record.request["user_input"] == "Harness Engineering"
    assert record.created_at.endswith("Z")

    await repository.mark_running("task_roundtrip")
    await repository.set_stage("task_roundtrip", stage="generating")
    await repository.mark_succeeded(
        "task_roundtrip",
        quiz_id="quiz_roundtrip",
        result={"title": "中文标题", "questions": []},
    )

    record = await repository.get("task_roundtrip")
    assert record is not None
    assert record.status == "succeeded"
    assert record.stage == "completed"
    assert record.quiz_id == "quiz_roundtrip"
    assert record.result == {"title": "中文标题", "questions": []}
    assert record.error_code is None


async def test_mark_failed_keeps_error_code(mysql_db: Database) -> None:
    repository = QuizTaskRepository(mysql_db)
    await repository.create(
        task_id="task_failed",
        user_id=7,
        request={"user_input": "RAG"},
        expires_at=expires_in(),
    )
    await repository.mark_running("task_failed")

    await repository.mark_failed("task_failed", code=4002, message="模型服务不可用")

    record = await repository.get("task_failed")
    assert record is not None
    assert record.status == "failed"
    assert record.stage == "failed"
    assert record.error_code == 4002
    assert record.error_message == "模型服务不可用"
    assert record.user_id == 7


async def test_fail_stale_marks_unfinished_tasks(mysql_db: Database) -> None:
    repository = QuizTaskRepository(mysql_db)
    await repository.create(
        task_id="task_pending",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(),
    )
    await repository.create(
        task_id="task_running",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(),
    )
    await repository.mark_running("task_running")
    await repository.create(
        task_id="task_done",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(),
    )
    await repository.mark_succeeded(
        "task_done", quiz_id="quiz_done", result={"title": "完成"}
    )

    assert await repository.fail_stale(message="服务重启") == 2

    pending = await repository.get("task_pending")
    running = await repository.get("task_running")
    done = await repository.get("task_done")
    assert pending is not None and pending.status == "failed"
    assert running is not None and running.status == "failed"
    assert done is not None and done.status == "succeeded"


async def test_purge_finished_only_removes_expired_tasks(mysql_db: Database) -> None:
    repository = QuizTaskRepository(mysql_db)
    await repository.create(
        task_id="task_old",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(-48),
    )
    await repository.mark_succeeded("task_old", quiz_id="quiz_old", result={})
    await repository.create(
        task_id="task_fresh",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(),
    )
    await repository.mark_succeeded("task_fresh", quiz_id="quiz_fresh", result={})
    await repository.create(
        task_id="task_active",
        user_id=None,
        request={"user_input": "RAG"},
        expires_at=expires_in(-48),
    )
    await repository.mark_running("task_active")

    assert await repository.purge_finished() == 1
    assert await repository.get("task_old") is None
    assert await repository.get("task_fresh") is not None
    assert await repository.get("task_active") is not None
