from __future__ import annotations

import pytest

from app.core.db import Database
from app.repositories.knowledge_repository import (
    InMemoryKnowledgeRepository,
    KnowledgeDocumentRecord,
    KnowledgeRepository,
)


def record(doc_id: str, user_id: int, **overrides: object) -> KnowledgeDocumentRecord:
    values: dict[str, object] = {
        "doc_id": doc_id,
        "user_id": user_id,
        "title": "客服培训手册",
        "filename": "training.pdf",
        "source_type": "pdf",
        "size_bytes": 2048,
        "chunk_count": 7,
        "status": "ready",
        "error_message": None,
        "created_at": "2026-11-01T08:00:00Z",
    }
    values.update(overrides)
    return KnowledgeDocumentRecord(**values)  # type: ignore[arg-type]


async def create(repo, doc_id: str, user_id: int, **overrides: object) -> None:
    payload = record(doc_id, user_id, **overrides)
    await repo.create(
        doc_id=payload.doc_id,
        user_id=payload.user_id,
        title=payload.title,
        filename=payload.filename,
        source_type=payload.source_type,
        size_bytes=payload.size_bytes,
        chunk_count=payload.chunk_count,
        status=payload.status,
    )


async def test_in_memory_create_and_get() -> None:
    repo = InMemoryKnowledgeRepository()
    await create(repo, "doc_1", 1)

    found = await repo.get("doc_1")

    assert found is not None
    assert found.title == "客服培训手册"
    assert found.chunk_count == 7
    assert found.status == "ready"
    assert found.created_at


async def test_in_memory_list_is_scoped_to_user() -> None:
    repo = InMemoryKnowledgeRepository()
    await create(repo, "doc_1", 1)
    await create(repo, "doc_2", 1)
    await create(repo, "doc_3", 2)

    assert {item.doc_id for item in await repo.list_by_user(1)} == {"doc_1", "doc_2"}
    assert [item.doc_id for item in await repo.list_by_user(2)] == ["doc_3"]
    assert await repo.count_by_user(1) == 2
    assert await repo.count_by_user(3) == 0


async def test_in_memory_delete_requires_owner() -> None:
    repo = InMemoryKnowledgeRepository()
    await create(repo, "doc_1", 1)

    assert await repo.delete("doc_1", user_id=2) is False
    assert await repo.get("doc_1") is not None
    assert await repo.delete("doc_1", user_id=1) is True
    assert await repo.get("doc_1") is None


async def test_in_memory_update_chunk_count() -> None:
    repo = InMemoryKnowledgeRepository()
    await create(repo, "doc_1", 1)

    await repo.mark_ready("doc_1", chunk_count=12)

    found = await repo.get("doc_1")
    assert found is not None
    assert found.chunk_count == 12
    assert found.status == "ready"


async def test_in_memory_mark_failed_records_error() -> None:
    repo = InMemoryKnowledgeRepository()
    await create(repo, "doc_1", 1, status="processing", chunk_count=0)

    await repo.mark_failed("doc_1", message="解析失败")

    found = await repo.get("doc_1")
    assert found is not None
    assert found.status == "failed"
    assert found.error_message == "解析失败"


pytestmark_integration = pytest.mark.integration


@pytest.mark.integration
async def test_mysql_knowledge_roundtrip(mysql_db: Database) -> None:
    repo = KnowledgeRepository(mysql_db)
    await create(repo, "doc_mysql", 42)
    await create(repo, "doc_mysql_other", 43)

    found = await repo.get("doc_mysql")
    assert found is not None
    assert found.user_id == 42
    assert found.source_type == "pdf"
    assert found.chunk_count == 7
    assert found.created_at.endswith("Z")

    assert [item.doc_id for item in await repo.list_by_user(42)] == ["doc_mysql"]
    assert await repo.count_by_user(42) == 1

    await repo.mark_ready("doc_mysql", chunk_count=9)
    updated = await repo.get("doc_mysql")
    assert updated is not None and updated.chunk_count == 9

    assert await repo.delete("doc_mysql", user_id=43) is False
    assert await repo.delete("doc_mysql", user_id=42) is True
    assert await repo.get("doc_mysql") is None
