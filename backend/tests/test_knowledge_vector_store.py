from __future__ import annotations

import math
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.knowledge.vector_store import ChromaKnowledgeStore, collection_name_for


class BagOfCharsEmbeddings(Embeddings):
    """确定性字符袋向量，便于在测试里验证召回顺序。"""

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


def chunk(text: str, doc_id: str, index: int, title: str = "文档") -> Document:
    return Document(
        page_content=text,
        metadata={
            "doc_id": doc_id,
            "title": title,
            "source_type": "txt",
            "chunk_index": index,
        },
    )


def build_store(tmp_path: Path) -> ChromaKnowledgeStore:
    return ChromaKnowledgeStore(
        persist_dir=tmp_path,
        embeddings=BagOfCharsEmbeddings(),
    )


def test_collection_name_is_per_user() -> None:
    assert collection_name_for(1) == "kb_user_1"
    assert collection_name_for(1) != collection_name_for(2)


async def test_add_and_search_returns_best_match(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    await store.add(
        user_id=1,
        documents=[
            chunk("退货政策：七天无理由退货，需要保留小票。", "doc_a", 0, "售后手册"),
            chunk("发货时效：下单后 24 小时内发出。", "doc_a", 1, "售后手册"),
        ],
    )

    hits = await store.search(user_id=1, query="退货政策是什么", top_k=2)

    assert hits
    assert "退货" in hits[0].content
    assert hits[0].doc_id == "doc_a"
    assert hits[0].title == "售后手册"
    assert hits[0].score >= hits[-1].score


async def test_search_filters_by_document(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    await store.add(
        user_id=1,
        documents=[
            chunk("退货政策：七天无理由退货。", "doc_a", 0),
            chunk("退货政策：跨境商品不支持无理由退货。", "doc_b", 0),
        ],
    )

    hits = await store.search(user_id=1, query="退货政策", top_k=5, doc_ids=["doc_b"])

    assert hits
    assert {hit.doc_id for hit in hits} == {"doc_b"}


async def test_search_is_isolated_between_users(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    await store.add(user_id=1, documents=[chunk("用户一的私有资料：内部报价单。", "doc_a", 0)])
    await store.add(user_id=2, documents=[chunk("用户二的私有资料：对外宣传稿。", "doc_b", 0)])

    hits = await store.search(user_id=2, query="内部报价单", top_k=5)

    assert hits
    assert {hit.doc_id for hit in hits} == {"doc_b"}


async def test_delete_document_removes_only_that_document(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    await store.add(
        user_id=1,
        documents=[
            chunk("文档 A 的内容", "doc_a", 0),
            chunk("文档 B 的内容", "doc_b", 0),
        ],
    )

    removed = await store.delete_document(user_id=1, doc_id="doc_a")

    assert removed == 1
    hits = await store.search(user_id=1, query="文档 A 的内容", top_k=5)
    assert {hit.doc_id for hit in hits} == {"doc_b"}


async def test_search_empty_collection_returns_empty(tmp_path: Path) -> None:
    store = build_store(tmp_path)

    assert await store.search(user_id=99, query="任意问题") == []


async def test_delete_missing_document_returns_zero(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    await store.add(user_id=1, documents=[chunk("内容", "doc_a", 0)])

    assert await store.delete_document(user_id=1, doc_id="doc_missing") == 0
