"""Chroma 向量库适配层：按用户划分 collection，全部调用放到线程池避免阻塞事件循环。"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

COLLECTION_PREFIX = "kb_user_"
_EXTRA_FIELDS = ("doc_id", "title", "source_type", "chunk_index")


def collection_name_for(user_id: int) -> str:
    return f"{COLLECTION_PREFIX}{user_id}"


@dataclass(frozen=True)
class ScoredChunk:
    doc_id: str
    title: str
    chunk_index: int
    content: str
    score: float


class ChromaKnowledgeStore:
    def __init__(self, *, persist_dir: Path | str, embeddings: Embeddings) -> None:
        self._persist_dir = str(persist_dir)
        self._embeddings = embeddings
        self._client: Any | None = None
        self._stores: dict[str, Chroma] = {}
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        if self._client is None:
            Path(self._persist_dir).mkdir(parents=True, exist_ok=True)
            # 同一进程内只能存在一个指向相同目录的 PersistentClient
            self._client = chromadb.PersistentClient(path=self._persist_dir)
        return self._client

    def _get_store(self, user_id: int) -> Chroma:
        name = collection_name_for(user_id)
        with self._lock:
            store = self._stores.get(name)
            if store is None:
                store = Chroma(
                    client=self._get_client(),
                    collection_name=name,
                    embedding_function=self._embeddings,
                    create_collection_if_not_exists=True,
                )
                self._stores[name] = store
            return store

    def _store_if_exists(self, user_id: int) -> Chroma | None:
        """检索时不要为陌生用户新建空 collection。"""
        name = collection_name_for(user_id)
        with self._lock:
            cached = self._stores.get(name)
        if cached is not None:
            return cached
        existing = {item.name for item in self._get_client().list_collections()}
        if name not in existing:
            return None
        return self._get_store(user_id)

    async def add(self, *, user_id: int, documents: Sequence[Document]) -> list[str]:
        if not documents:
            return []
        store = self._get_store(user_id)
        payload = [
            Document(
                page_content=item.page_content,
                metadata={
                    **{key: item.metadata.get(key) for key in _EXTRA_FIELDS},
                    "user_id": user_id,
                },
            )
            for item in documents
        ]
        return await asyncio.to_thread(store.add_documents, payload)

    async def search(
        self,
        *,
        user_id: int,
        query: str,
        top_k: int = 5,
        doc_ids: Sequence[str] = (),
    ) -> list[ScoredChunk]:
        question = (query or "").strip()
        if not question:
            return []
        store = self._store_if_exists(user_id)
        if store is None:
            return []

        filter_value: dict[str, Any] | None = None
        ids = [str(item) for item in doc_ids if item]
        if ids:
            filter_value = {"doc_id": {"$in": ids}}

        try:
            results = await asyncio.to_thread(
                store.similarity_search_with_score,
                question,
                k=max(1, top_k),
                filter=filter_value,
            )
        except Exception as exc:  # noqa: BLE001 - 向量库异常由上层降级
            logger.warning("知识库检索失败 error=%s", type(exc).__name__)
            return []

        chunks: list[ScoredChunk] = []
        for document, distance in results:
            metadata = document.metadata or {}
            chunks.append(
                ScoredChunk(
                    doc_id=str(metadata.get("doc_id") or ""),
                    title=str(metadata.get("title") or ""),
                    chunk_index=int(metadata.get("chunk_index") or 0),
                    content=document.page_content,
                    # 距离越小越相关，转换成越大越相关的分数便于展示
                    score=round(1.0 / (1.0 + float(distance)), 6),
                )
            )
        return chunks

    async def delete_document(self, *, user_id: int, doc_id: str) -> int:
        store = self._store_if_exists(user_id)
        if store is None:
            return 0
        matched = await asyncio.to_thread(
            store.get, where={"doc_id": doc_id}, include=[]
        )
        ids = list(matched.get("ids") or [])
        if not ids:
            return 0
        await asyncio.to_thread(store.delete, ids=ids)
        return len(ids)

    async def count(self, *, user_id: int) -> int:
        store = self._store_if_exists(user_id)
        if store is None:
            return 0
        collected = await asyncio.to_thread(store.get, include=[])
        return len(collected.get("ids") or [])
