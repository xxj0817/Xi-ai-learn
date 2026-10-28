"""异步出题任务的数据访问：MySQL 实现 + 内存降级实现。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol

import aiomysql

from app.core.db import Database

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("pending", "running", "queued")
TERMINAL_STATUSES = ("succeeded", "failed")


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        logger.warning("任务 JSON 字段解析失败，返回原始值")
        return value


def _parse_code(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class QuizTaskRecord:
    task_id: str
    user_id: int | None
    status: str
    stage: str
    request: dict[str, Any]
    result: dict[str, Any] | None
    quiz_id: str | None
    error_code: int | None
    error_message: str | None
    created_at: str
    updated_at: str
    expires_at: str = ""


class QuizTaskRepositoryProtocol(Protocol):
    async def create(
        self,
        *,
        task_id: str,
        user_id: int | None,
        request: dict[str, Any],
        expires_at: datetime,
    ) -> None: ...

    async def mark_running(self, task_id: str) -> None: ...

    async def set_stage(self, task_id: str, *, stage: str) -> None: ...

    async def mark_succeeded(
        self, task_id: str, *, quiz_id: str, result: dict[str, Any]
    ) -> None: ...

    async def mark_failed(
        self, task_id: str, *, code: int, message: str
    ) -> None: ...

    async def get(self, task_id: str) -> QuizTaskRecord | None: ...

    async def fail_stale(self, *, message: str, code: int = 5001) -> int: ...

    async def purge_finished(self) -> int: ...


_SELECT_COLUMNS = (
    "task_id, user_id, status, stage, request_json, result_json, "
    "quiz_id, error_code, error_message, created_at, updated_at, expires_at"
)


def _row_to_record(row: tuple[Any, ...]) -> QuizTaskRecord:
    return QuizTaskRecord(
        task_id=str(row[0]),
        user_id=int(row[1]) if row[1] is not None else None,
        status=str(row[2]),
        stage=str(row[3]),
        request=_loads(row[4]) or {},
        result=_loads(row[5]),
        quiz_id=str(row[6]) if row[6] else None,
        error_code=_parse_code(row[7]),
        error_message=str(row[8]) if row[8] else None,
        created_at=_iso(row[9]),
        updated_at=_iso(row[10]),
        expires_at=_iso(row[11]),
    )


class QuizTaskRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        task_id: str,
        user_id: int | None,
        request: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "INSERT INTO quiz_tasks "
                    "(task_id, user_id, status, stage, request_json, expires_at) "
                    "VALUES (%s, %s, 'pending', 'queued', %s, %s)",
                    (task_id, user_id, _dumps(request), _to_naive_utc(expires_at)),
                )

    async def mark_running(self, task_id: str) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE quiz_tasks SET status = 'running', stage = 'researching' "
                    "WHERE task_id = %s AND status = 'pending'",
                    (task_id,),
                )

    async def set_stage(self, task_id: str, *, stage: str) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE quiz_tasks SET stage = %s "
                    "WHERE task_id = %s AND status = 'running'",
                    (stage, task_id),
                )

    async def mark_succeeded(
        self, task_id: str, *, quiz_id: str, result: dict[str, Any]
    ) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE quiz_tasks SET status = 'succeeded', stage = 'completed', "
                    "quiz_id = %s, result_json = %s, error_code = NULL, error_message = NULL, "
                    "finished_at = CURRENT_TIMESTAMP WHERE task_id = %s",
                    (quiz_id, _dumps(result), task_id),
                )

    async def mark_failed(
        self, task_id: str, *, code: int, message: str
    ) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE quiz_tasks SET status = 'failed', stage = 'failed', error_code = %s, "
                    "error_message = %s, finished_at = CURRENT_TIMESTAMP "
                    "WHERE task_id = %s AND status IN ('pending', 'running', 'queued')",
                    (str(code), message, task_id),
                )

    async def get(self, task_id: str) -> QuizTaskRecord | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM quiz_tasks WHERE task_id = %s",
                    (task_id,),
                )
                row = await cursor.fetchone()
        return _row_to_record(row) if row is not None else None

    async def fail_stale(self, *, message: str, code: int = 5001) -> int:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE quiz_tasks SET status = 'failed', stage = 'failed', error_code = %s, "
                    "error_message = %s, finished_at = CURRENT_TIMESTAMP "
                    "WHERE status IN ('pending', 'running', 'queued')",
                    (str(code), message),
                )
                return int(cursor.rowcount or 0)

    async def purge_finished(self) -> int:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "DELETE FROM quiz_tasks WHERE status IN ('succeeded', 'failed') "
                    "AND expires_at IS NOT NULL AND expires_at < %s",
                    (_to_naive_utc(datetime.now(timezone.utc)),),
                )
                return int(cursor.rowcount or 0)


class InMemoryQuizTaskRepository:
    """未启用 MySQL 或连接失败时的降级实现，仅当前进程可见。"""

    def __init__(self) -> None:
        self._records: dict[str, QuizTaskRecord] = {}

    async def create(
        self,
        *,
        task_id: str,
        user_id: int | None,
        request: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        now = _now_iso()
        self._records[task_id] = QuizTaskRecord(
            task_id=task_id,
            user_id=user_id,
            status="pending",
            stage="queued",
            request=dict(request),
            result=None,
            quiz_id=None,
            error_code=None,
            error_message=None,
            created_at=now,
            updated_at=now,
            expires_at=expires_at.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        )

    def _replace(self, task_id: str, **changes: Any) -> None:
        record = self._records.get(task_id)
        if record is None:
            return
        self._records[task_id] = replace(record, updated_at=_now_iso(), **changes)

    async def mark_running(self, task_id: str) -> None:
        record = self._records.get(task_id)
        if record is None or record.status != "pending":
            return
        self._replace(task_id, status="running", stage="researching")

    async def set_stage(self, task_id: str, *, stage: str) -> None:
        record = self._records.get(task_id)
        if record is None or record.status != "running":
            return
        self._replace(task_id, stage=stage)

    async def mark_succeeded(
        self, task_id: str, *, quiz_id: str, result: dict[str, Any]
    ) -> None:
        self._replace(
            task_id,
            status="succeeded",
            stage="completed",
            quiz_id=quiz_id,
            result=result,
            error_code=None,
            error_message=None,
        )

    async def mark_failed(
        self, task_id: str, *, code: int, message: str
    ) -> None:
        record = self._records.get(task_id)
        if record is None or record.status not in ACTIVE_STATUSES:
            return
        self._replace(
            task_id,
            status="failed",
            stage="failed",
            error_code=code,
            error_message=message,
        )

    async def get(self, task_id: str) -> QuizTaskRecord | None:
        record = self._records.get(task_id)
        return replace(record) if record is not None else None

    async def fail_stale(self, *, message: str, code: int = 5001) -> int:
        stale = [
            task_id
            for task_id, record in self._records.items()
            if record.status in ACTIVE_STATUSES
        ]
        for task_id in stale:
            self._replace(
                task_id,
                status="failed",
                stage="failed",
                error_code=code,
                error_message=message,
            )
        return len(stale)

    async def purge_finished(self) -> int:
        now = datetime.now(timezone.utc)
        expired: list[str] = []
        for task_id, record in self._records.items():
            if record.status not in TERMINAL_STATUSES:
                continue
            expires_at = _parse_iso(record.expires_at)
            if expires_at is not None and expires_at < now:
                expired.append(task_id)
        for task_id in expired:
            self._records.pop(task_id, None)
        return len(expired)
