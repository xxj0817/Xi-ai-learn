"""知识库文档元数据访问：MySQL 实现 + 内存降级实现。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Protocol

import aiomysql

from app.core.db import Database

logger = logging.getLogger(__name__)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


@dataclass(frozen=True)
class KnowledgeDocumentRecord:
    doc_id: str
    user_id: int
    title: str
    filename: str
    source_type: str
    size_bytes: int
    chunk_count: int
    status: str
    error_message: str | None
    created_at: str


class KnowledgeRepositoryProtocol(Protocol):
    async def create(
        self,
        *,
        doc_id: str,
        user_id: int,
        title: str,
        filename: str,
        source_type: str,
        size_bytes: int,
        chunk_count: int,
        status: str,
    ) -> None: ...

    async def get(self, doc_id: str) -> KnowledgeDocumentRecord | None: ...

    async def list_by_user(self, user_id: int) -> list[KnowledgeDocumentRecord]: ...

    async def count_by_user(self, user_id: int) -> int: ...

    async def mark_ready(self, doc_id: str, *, chunk_count: int) -> None: ...

    async def mark_failed(self, doc_id: str, *, message: str) -> None: ...

    async def delete(self, doc_id: str, *, user_id: int) -> bool: ...


_SELECT_COLUMNS = (
    "doc_id, user_id, title, filename, source_type, size_bytes, chunk_count, "
    "status, error_message, created_at"
)


def _row_to_record(row: tuple[Any, ...]) -> KnowledgeDocumentRecord:
    return KnowledgeDocumentRecord(
        doc_id=str(row[0]),
        user_id=int(row[1]),
        title=str(row[2] or ""),
        filename=str(row[3] or ""),
        source_type=str(row[4] or "txt"),
        size_bytes=int(row[5] or 0),
        chunk_count=int(row[6] or 0),
        status=str(row[7] or "ready"),
        error_message=str(row[8]) if row[8] else None,
        created_at=_iso(row[9]),
    )


class KnowledgeRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(
        self,
        *,
        doc_id: str,
        user_id: int,
        title: str,
        filename: str,
        source_type: str,
        size_bytes: int,
        chunk_count: int,
        status: str,
    ) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "INSERT INTO knowledge_documents "
                    "(doc_id, user_id, title, filename, source_type, size_bytes, chunk_count, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        doc_id,
                        user_id,
                        title[:255],
                        filename[:255],
                        source_type,
                        size_bytes,
                        chunk_count,
                        status,
                    ),
                )

    async def get(self, doc_id: str) -> KnowledgeDocumentRecord | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM knowledge_documents WHERE doc_id = %s",
                    (doc_id,),
                )
                row = await cursor.fetchone()
        return _row_to_record(row) if row is not None else None

    async def list_by_user(self, user_id: int) -> list[KnowledgeDocumentRecord]:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM knowledge_documents "
                    "WHERE user_id = %s ORDER BY id DESC",
                    (user_id,),
                )
                rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]

    async def count_by_user(self, user_id: int) -> int:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM knowledge_documents WHERE user_id = %s",
                    (user_id,),
                )
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def mark_ready(self, doc_id: str, *, chunk_count: int) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE knowledge_documents SET status = 'ready', chunk_count = %s, "
                    "error_message = NULL WHERE doc_id = %s",
                    (chunk_count, doc_id),
                )

    async def mark_failed(self, doc_id: str, *, message: str) -> None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "UPDATE knowledge_documents SET status = 'failed', error_message = %s "
                    "WHERE doc_id = %s",
                    (message[:255], doc_id),
                )

    async def delete(self, doc_id: str, *, user_id: int) -> bool:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "DELETE FROM knowledge_documents WHERE doc_id = %s AND user_id = %s",
                    (doc_id, user_id),
                )
                return bool(cursor.rowcount)


class InMemoryKnowledgeRepository:
    """未启用 MySQL 时的降级实现，仅当前进程可见。"""

    def __init__(self) -> None:
        self._records: dict[str, KnowledgeDocumentRecord] = {}
        self._order: list[str] = []

    async def create(
        self,
        *,
        doc_id: str,
        user_id: int,
        title: str,
        filename: str,
        source_type: str,
        size_bytes: int,
        chunk_count: int,
        status: str,
    ) -> None:
        if doc_id not in self._records:
            self._order.insert(0, doc_id)
        self._records[doc_id] = KnowledgeDocumentRecord(
            doc_id=doc_id,
            user_id=user_id,
            title=title,
            filename=filename,
            source_type=source_type,
            size_bytes=size_bytes,
            chunk_count=chunk_count,
            status=status,
            error_message=None,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    async def get(self, doc_id: str) -> KnowledgeDocumentRecord | None:
        return self._records.get(doc_id)

    async def list_by_user(self, user_id: int) -> list[KnowledgeDocumentRecord]:
        return [
            self._records[doc_id]
            for doc_id in self._order
            if doc_id in self._records and self._records[doc_id].user_id == user_id
        ]

    async def count_by_user(self, user_id: int) -> int:
        return sum(1 for item in self._records.values() if item.user_id == user_id)

    def _replace(self, doc_id: str, **changes: Any) -> None:
        existing = self._records.get(doc_id)
        if existing is None:
            return
        self._records[doc_id] = replace(existing, **changes)

    async def mark_ready(self, doc_id: str, *, chunk_count: int) -> None:
        self._replace(doc_id, status="ready", chunk_count=chunk_count, error_message=None)

    async def mark_failed(self, doc_id: str, *, message: str) -> None:
        self._replace(doc_id, status="failed", error_message=message[:255])

    async def delete(self, doc_id: str, *, user_id: int) -> bool:
        existing = self._records.get(doc_id)
        if existing is None or existing.user_id != user_id:
            return False
        self._records.pop(doc_id, None)
        if doc_id in self._order:
            self._order.remove(doc_id)
        return True
