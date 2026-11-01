from __future__ import annotations

import math
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from app.core.config import Settings
from app.core.exceptions import InvalidInput, KnowledgeUnavailable, ResourceNotFound
from app.knowledge.vector_store import ChromaKnowledgeStore
from app.models.knowledge import KnowledgeDocumentStatus
from app.repositories.knowledge_repository import InMemoryKnowledgeRepository
from app.services.knowledge_service import KnowledgeService


class BagOfCharsEmbeddings(Embeddings):
    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for char in text:
            vector[ord(char) % self._dim] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FailingEmbeddings(BagOfCharsEmbeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding service down")


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
        "kb_upload_dir": str(tmp_path / "uploads"),
        "kb_chunk_size": 200,
        "kb_chunk_overlap": 20,
        "kb_top_k": 3,
        "kb_context_max_chars": 500,
    }
    values.update(overrides)
    return Settings(**values)


def build_service(
    tmp_path: Path,
    *,
    settings: Settings | None = None,
    embeddings: Embeddings | None = None,
) -> tuple[KnowledgeService, InMemoryKnowledgeRepository]:
    settings = settings or make_settings(tmp_path)
    repository = InMemoryKnowledgeRepository()
    store = ChromaKnowledgeStore(
        persist_dir=tmp_path / "chroma",
        embeddings=embeddings or BagOfCharsEmbeddings(),
    )
    service = KnowledgeService(
        settings,
        repository=repository,
        vector_store=store,
        upload_root=Path(settings.kb_upload_dir),
    )
    return service, repository


async def test_upload_markdown_builds_searchable_document(tmp_path: Path) -> None:
    service, repo = build_service(tmp_path)
    content = "# 客服培训\n\n退货政策：七天无理由退货，需要保留小票。\n".encode()

    document = await service.upload(user_id=1, filename="培训.md", data=content)

    assert document.status is KnowledgeDocumentStatus.ready
    assert document.chunk_count >= 1
    assert document.title == "客服培训"
    assert await repo.count_by_user(1) == 1

    result = await service.search(user_id=1, query="退货政策")
    assert result.chunks
    assert "退货" in result.chunks[0].content
    assert result.context


async def test_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    service, repo = build_service(tmp_path)

    with pytest.raises(InvalidInput):
        await service.upload(user_id=1, filename="video.mp4", data=b"binary")

    assert await repo.count_by_user(1) == 0


async def test_upload_rejects_oversized_file(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, kb_max_file_bytes=1024)
    service, repo = build_service(tmp_path, settings=settings)

    with pytest.raises(InvalidInput):
        await service.upload(user_id=1, filename="big.txt", data=b"a" * 2000)

    assert await repo.count_by_user(1) == 0


async def test_upload_enforces_document_quota(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, kb_max_documents_per_user=1)
    service, _repo = build_service(tmp_path, settings=settings)
    await service.upload(user_id=1, filename="a.txt", data="第一份资料".encode())

    with pytest.raises(InvalidInput):
        await service.upload(user_id=1, filename="b.txt", data="第二份资料".encode())


async def test_upload_cleans_up_when_embedding_fails(tmp_path: Path) -> None:
    service, repo = build_service(tmp_path, embeddings=FailingEmbeddings())

    with pytest.raises(KnowledgeUnavailable):
        await service.upload(user_id=1, filename="a.md", data=b"# title\n\ncontent")

    assert await repo.count_by_user(1) == 0
    upload_root = tmp_path / "uploads" / "1"
    assert not upload_root.exists() or not any(upload_root.iterdir())


async def test_add_text_document_is_searchable(tmp_path: Path) -> None:
    service, _repo = build_service(tmp_path)

    document = await service.add_text(
        user_id=2,
        title="内部 FAQ",
        content="工单分级规则：P0 为线上不可用，P1 为功能受损。",
    )

    assert document.source_type.value == "txt"
    result = await service.search(user_id=2, query="工单分级")
    assert result.chunks
    assert "工单分级" in result.chunks[0].content


async def test_delete_removes_document_and_vectors(tmp_path: Path) -> None:
    service, repo = build_service(tmp_path)
    document = await service.upload(user_id=1, filename="a.md", data=b"# A\n\nunique-word-alpha")

    await service.delete(user_id=1, doc_id=document.doc_id)

    assert await repo.get(document.doc_id) is None
    hits = await service.search(user_id=1, query="unique-word-alpha")
    assert hits.chunks == []


async def test_delete_unknown_document_raises(tmp_path: Path) -> None:
    service, _repo = build_service(tmp_path)

    with pytest.raises(ResourceNotFound):
        await service.delete(user_id=1, doc_id="doc_missing")


async def test_delete_rejects_other_users_document(tmp_path: Path) -> None:
    service, repo = build_service(tmp_path)
    document = await service.upload(user_id=1, filename="a.md", data=b"# A\n\ncontent")

    with pytest.raises(ResourceNotFound):
        await service.delete(user_id=2, doc_id=document.doc_id)

    assert await repo.get(document.doc_id) is not None


async def test_resolve_doc_ids_checks_ownership(tmp_path: Path) -> None:
    service, _repo = build_service(tmp_path)
    document = await service.upload(user_id=1, filename="a.md", data=b"# A\n\ncontent")

    assert await service.resolve_doc_ids(1, [document.doc_id]) == [document.doc_id]
    assert await service.resolve_doc_ids(1, []) == [document.doc_id]

    with pytest.raises(InvalidInput):
        await service.resolve_doc_ids(2, [document.doc_id])


async def test_search_without_documents_returns_empty(tmp_path: Path) -> None:
    service, _repo = build_service(tmp_path)

    result = await service.search(user_id=5, query="任意问题")

    assert result.chunks == []
    assert result.context == ""


async def test_search_respects_context_char_budget(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, kb_context_max_chars=200, kb_top_k=5)
    service, _repo = build_service(tmp_path, settings=settings)
    await service.upload(
        user_id=1,
        filename="long.md",
        data=("# 长文档\n\n" + "退货政策说明。" * 200).encode(),
    )

    result = await service.search(user_id=1, query="退货政策")

    assert len(result.context) <= 200
    assert len(result.chunks) >= 1


async def test_list_documents_returns_user_documents(tmp_path: Path) -> None:
    service, _repo = build_service(tmp_path)
    await service.upload(user_id=1, filename="a.md", data=b"# A\n\ncontent one")
    await service.upload(user_id=2, filename="b.md", data=b"# B\n\ncontent two")

    listing = await service.list_documents(1)

    assert listing.total == 1
    assert listing.items[0].title == "A"
