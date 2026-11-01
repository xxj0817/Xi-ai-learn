"""知识库服务：上传解析、切分入库、列举、删除与检索。"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from app.core.config import Settings
from app.core.exceptions import InvalidInput, KnowledgeUnavailable, ResourceNotFound
from app.knowledge.loaders import detect_source_type, load_bytes
from app.knowledge.splitter import split_text
from app.knowledge.vector_store import ScoredChunk
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentList,
    KnowledgeDocumentStatus,
    KnowledgeSourceType,
)
from app.repositories.knowledge_repository import (
    KnowledgeDocumentRecord,
    KnowledgeRepositoryProtocol,
)
from app.utils.id_generator import new_knowledge_doc_id

logger = logging.getLogger(__name__)

_LIST_ITEM_LIMIT = 200
_HEADING_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
_FILENAME_STEM_RE = re.compile(r"[\\/]")


class VectorStoreProtocol(Protocol):
    async def add(self, *, user_id: int, documents: Sequence[object]) -> list[str]: ...

    async def search(
        self,
        *,
        user_id: int,
        query: str,
        top_k: int = 5,
        doc_ids: Sequence[str] = (),
    ) -> list[ScoredChunk]: ...

    async def delete_document(self, *, user_id: int, doc_id: str) -> int: ...


@dataclass(frozen=True)
class KnowledgeSearchResult:
    chunks: list[ScoredChunk]
    context: str


def _derive_title(filename: str, text: str) -> str:
    match = _HEADING_RE.search(text or "")
    if match:
        return match.group(1).strip()[:120]
    stem = _FILENAME_STEM_RE.split(filename or "")[-1]
    stem = stem.rsplit(".", 1)[0].strip()
    if stem:
        return stem[:120]
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    return (first_line or "未命名文档")[:120]


def build_knowledge_service(
    settings: Settings, db: object | None
) -> "KnowledgeService | None":
    """构造知识库服务；未启用或未配置嵌入服务时返回 None，由接口层返回 503。"""
    if not settings.kb_enabled:
        return None

    embeddings_builder = _EMBEDDINGS_BUILDER
    try:
        embeddings = embeddings_builder(settings)
    except Exception as exc:  # noqa: BLE001 - 未配置 Key 时不阻塞应用启动
        logger.warning("知识库嵌入不可用 error=%s", type(exc).__name__)
        return None

    from app.knowledge.vector_store import ChromaKnowledgeStore

    base_dir = Path(__file__).resolve().parents[2]
    persist_dir = (
        Path(settings.chroma_persist_dir).expanduser()
        if settings.chroma_persist_dir.strip()
        else base_dir / "data" / "chroma"
    )
    upload_root = (
        Path(settings.kb_upload_dir).expanduser()
        if settings.kb_upload_dir.strip()
        else base_dir / "data" / "uploads"
    )

    if db is not None:
        from app.repositories.knowledge_repository import KnowledgeRepository

        repository: KnowledgeRepositoryProtocol = KnowledgeRepository(db)  # type: ignore[arg-type]
    else:
        logger.warning("未启用 MySQL，知识库元数据将使用进程内存储，重启后丢失")
        from app.repositories.knowledge_repository import InMemoryKnowledgeRepository

        repository = InMemoryKnowledgeRepository()

    store = ChromaKnowledgeStore(persist_dir=persist_dir, embeddings=embeddings)
    return KnowledgeService(
        settings,
        repository=repository,
        vector_store=store,
        upload_root=upload_root,
    )


_DEFAULTS_LOADER = "default"


def _default_embeddings_builder(settings: Settings):  # type: ignore[no-untyped-def]
    from app.knowledge.embeddings import build_embeddings

    return build_embeddings(settings)


_EMBEDDINGS_BUILDER = _default_embeddings_builder


class KnowledgeService:
    def __init__(
        self,
        settings: Settings,
        *,
        repository: KnowledgeRepositoryProtocol,
        vector_store: VectorStoreProtocol,
        upload_root: Path,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._vector_store = vector_store
        self._upload_root = Path(upload_root)

    async def upload(self, *, user_id: int, filename: str, data: bytes) -> KnowledgeDocument:
        source_type = detect_source_type(filename)
        if not data:
            raise InvalidInput("文件内容为空，请重新选择文件")
        if len(data) > self._settings.kb_max_file_bytes:
            limit_mb = self._settings.kb_max_file_bytes / (1024 * 1024)
            raise InvalidInput(f"文件过大，请上传 {limit_mb:.0f}MB 以内的文档")
        await self._ensure_quota(user_id)

        text = await asyncio.to_thread(load_bytes, filename, data)
        title = _derive_title(filename, text)
        doc_id = new_knowledge_doc_id()

        saved_path = await asyncio.to_thread(
            self._save_file, user_id, doc_id, source_type, data, filename
        )
        try:
            chunk_count = await self._index(
                user_id=user_id,
                doc_id=doc_id,
                title=title,
                source_type=source_type,
                text=text,
            )
        except Exception:
            await self._cleanup(user_id=user_id, doc_id=doc_id, path=saved_path)
            raise

        await self._repository.create(
            doc_id=doc_id,
            user_id=user_id,
            title=title,
            filename=filename[:255],
            source_type=source_type.value,
            size_bytes=len(data),
            chunk_count=chunk_count,
            status=KnowledgeDocumentStatus.ready.value,
        )
        record = await self._repository.get(doc_id)
        if record is None:
            raise KnowledgeUnavailable()
        logger.info("知识库文档入库完成 doc_id=%s chunks=%s", doc_id, chunk_count)
        return self._to_model(record)

    async def add_text(self, *, user_id: int, title: str, content: str) -> KnowledgeDocument:
        text = (content or "").strip()
        if not text:
            raise InvalidInput("正文内容不能为空")
        if len(text) > self._settings.kb_max_text_chars:
            raise InvalidInput(f"正文过长，请控制在 {self._settings.kb_max_text_chars} 字以内")
        await self._ensure_quota(user_id)

        doc_id = new_knowledge_doc_id()
        clean_title = (title or "").strip()[:120] or _derive_title("", text)
        chunk_count = await self._index(
            user_id=user_id,
            doc_id=doc_id,
            title=clean_title,
            source_type=KnowledgeSourceType.txt,
            text=text,
        )
        await self._repository.create(
            doc_id=doc_id,
            user_id=user_id,
            title=clean_title,
            filename="",
            source_type=KnowledgeSourceType.txt.value,
            size_bytes=len(text.encode("utf-8")),
            chunk_count=chunk_count,
            status=KnowledgeDocumentStatus.ready.value,
        )
        record = await self._repository.get(doc_id)
        if record is None:
            raise KnowledgeUnavailable()
        return self._to_model(record)

    async def list_documents(self, user_id: int) -> KnowledgeDocumentList:
        records = await self._repository.list_by_user(user_id)
        items = [self._to_model(record) for record in records[:_LIST_ITEM_LIMIT]]
        return KnowledgeDocumentList(items=items, total=len(records), enabled=True)

    async def delete(self, *, user_id: int, doc_id: str) -> None:
        record = await self._repository.get(doc_id)
        if record is None or record.user_id != user_id:
            raise ResourceNotFound("知识库文档不存在")

        try:
            await self._vector_store.delete_document(user_id=user_id, doc_id=doc_id)
        except Exception as exc:  # noqa: BLE001 - 向量清理失败不阻塞元数据删除
            logger.warning("向量删除失败 doc_id=%s error=%s", doc_id, type(exc).__name__)

        deleted = await self._repository.delete(doc_id, user_id=user_id)
        if not deleted:
            raise ResourceNotFound("知识库文档不存在")
        await asyncio.to_thread(self._remove_file, user_id, doc_id)

    async def resolve_doc_ids(self, user_id: int, requested: Sequence[str]) -> list[str]:
        """校验文档归属；未指定时返回该用户全部可用文档。"""
        records = await self._repository.list_by_user(user_id)
        ready = [item for item in records if item.status == KnowledgeDocumentStatus.ready.value]
        if not requested:
            return [item.doc_id for item in ready[: self._settings.kb_max_documents_per_quiz]]

        available = {item.doc_id for item in ready}
        selected: list[str] = []
        for doc_id in requested:
            if doc_id not in available:
                raise InvalidInput("知识库文档不存在或尚未就绪，请重新选择")
            selected.append(doc_id)
        return selected[: self._settings.kb_max_documents_per_quiz]

    async def search(
        self,
        *,
        user_id: int,
        query: str,
        doc_ids: Sequence[str] = (),
        top_k: int | None = None,
        max_chars: int | None = None,
    ) -> KnowledgeSearchResult:
        limit = top_k or self._settings.kb_top_k
        budget = max_chars or self._settings.kb_context_max_chars
        try:
            chunks = await self._vector_store.search(
                user_id=user_id,
                query=query,
                top_k=limit,
                doc_ids=doc_ids,
            )
        except Exception as exc:  # noqa: BLE001 - 检索失败降级为空结果
            logger.warning("知识库检索失败 error=%s", type(exc).__name__)
            return KnowledgeSearchResult(chunks=[], context="")

        kept: list[ScoredChunk] = []
        parts: list[str] = []
        used = 0
        for chunk in chunks:
            prefix = f"【{chunk.title or '知识库'}】"
            separator_cost = 2 if parts else 0  # "\n\n"
            remaining = budget - used - separator_cost - len(prefix)
            if remaining <= 0:
                break
            snippet = chunk.content[:remaining]
            if not snippet.strip():
                continue
            kept.append(
                ScoredChunk(
                    doc_id=chunk.doc_id,
                    title=chunk.title,
                    chunk_index=chunk.chunk_index,
                    content=snippet,
                    score=chunk.score,
                )
            )
            parts.append(prefix + snippet)
            used += separator_cost + len(prefix) + len(snippet)
        return KnowledgeSearchResult(chunks=kept, context="\n\n".join(parts))

    async def _index(
        self,
        *,
        user_id: int,
        doc_id: str,
        title: str,
        source_type: KnowledgeSourceType,
        text: str,
    ) -> int:
        chunks = split_text(
            text,
            doc_id=doc_id,
            title=title,
            source_type=source_type,
            chunk_size=self._settings.kb_chunk_size,
            chunk_overlap=self._settings.kb_chunk_overlap,
        )
        try:
            await self._vector_store.add(user_id=user_id, documents=chunks)
        except Exception as exc:  # noqa: BLE001 - 嵌入失败统一转换为可诊断错误
            logger.warning("知识库向量化失败 doc_id=%s error=%s", doc_id, type(exc).__name__)
            raise KnowledgeUnavailable("知识库向量化失败，请稍后重试") from exc
        return len(chunks)

    async def _ensure_quota(self, user_id: int) -> None:
        count = await self._repository.count_by_user(user_id)
        if count >= self._settings.kb_max_documents_per_user:
            raise InvalidInput(
                f"知识库文档数量已达上限（{self._settings.kb_max_documents_per_user} 个），请先删除旧文档"
            )

    async def _cleanup(self, *, user_id: int, doc_id: str, path: Path | None) -> None:
        try:
            await self._vector_store.delete_document(user_id=user_id, doc_id=doc_id)
        except Exception as exc:  # noqa: BLE001 - 清理失败仅记录
            logger.warning("清理向量失败 doc_id=%s error=%s", doc_id, type(exc).__name__)
        if path is not None:
            await asyncio.to_thread(self._remove_path, path)

    def _save_file(
        self,
        user_id: int,
        doc_id: str,
        source_type: KnowledgeSourceType,
        data: bytes,
        filename: str,
    ) -> Path:
        directory = self._upload_root / str(user_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{doc_id}.{source_type.value}"
        target.write_bytes(data)
        logger.debug("知识库文件已保存 file=%s size=%s", target.name, len(data))
        return target

    def _remove_file(self, user_id: int, doc_id: str) -> None:
        directory = self._upload_root / str(user_id)
        if not directory.is_dir():
            return
        for path in directory.glob(f"{doc_id}.*"):
            self._remove_path(path)

    @staticmethod
    def _remove_path(path: Path) -> None:
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:  # noqa: BLE001 - 清理失败不影响主流程
            logger.warning("知识库文件清理失败 file=%s error=%s", path.name, type(exc).__name__)

    @staticmethod
    def _to_model(record: KnowledgeDocumentRecord) -> KnowledgeDocument:
        return KnowledgeDocument(
            doc_id=record.doc_id,
            title=record.title,
            source_type=KnowledgeSourceType(record.source_type),
            size_bytes=record.size_bytes,
            chunk_count=record.chunk_count,
            status=KnowledgeDocumentStatus(record.status),
            created_at=record.created_at,
        )
