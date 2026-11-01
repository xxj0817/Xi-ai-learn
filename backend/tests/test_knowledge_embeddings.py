from __future__ import annotations

import pytest
from langchain_core.embeddings import Embeddings

from app.core.config import Settings
from app.knowledge.embeddings import KnowledgeEmbeddings, build_embeddings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
    }
    values.update(overrides)
    return Settings(**values)


class RecordingEmbeddings(Embeddings):
    """记录每次调用的批大小，返回确定性向量。"""

    def __init__(self) -> None:
        self.batches: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [float(len(text)), 1.0]


def test_build_embeddings_requires_dashscope_key() -> None:
    with pytest.raises(RuntimeError):
        build_embeddings(make_settings(dashscope_api_key=""))


def test_build_embeddings_configures_compatible_endpoint() -> None:
    settings = make_settings(
        dashscope_api_key="sk-test",
        embedding_dimensions=768,
    )

    embeddings = build_embeddings(settings)

    assert isinstance(embeddings, KnowledgeEmbeddings)
    inner = embeddings.inner
    assert inner.model == "text-embedding-v4"
    assert str(inner.openai_api_base) == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert inner.dimensions == 768
    # 百炼单次最多 10 条，必须显式限制批大小
    assert inner.chunk_size == 10
    # 必须关闭 tiktoken 预编码，否则会发送 base64 向量而不被百炼接受
    assert inner.check_embedding_ctx_length is False


def test_knowledge_embeddings_caps_batch_size() -> None:
    inner = RecordingEmbeddings()
    embeddings = KnowledgeEmbeddings(inner, batch_size=10)

    vectors = embeddings.embed_documents([f"文本{index}" for index in range(25)])

    assert [len(batch) for batch in inner.batches] == [10, 10, 5]
    assert len(vectors) == 25


def test_knowledge_embeddings_handles_empty_input() -> None:
    inner = RecordingEmbeddings()
    embeddings = KnowledgeEmbeddings(inner, batch_size=10)

    assert embeddings.embed_documents([]) == []
    assert inner.batches == []


def test_knowledge_embeddings_delegates_query() -> None:
    inner = RecordingEmbeddings()
    embeddings = KnowledgeEmbeddings(inner, batch_size=10)

    vector = embeddings.embed_query("退货政策")

    assert vector == [4.0, 1.0]
    assert inner.query_calls == ["退货政策"]


async def test_knowledge_embeddings_supports_async_batches() -> None:
    inner = RecordingEmbeddings()
    embeddings = KnowledgeEmbeddings(inner, batch_size=3)

    vectors = await embeddings.aembed_documents([f"t{index}" for index in range(7)])

    assert [len(batch) for batch in inner.batches] == [3, 3, 1]
    assert len(vectors) == 7


async def test_knowledge_embeddings_async_query() -> None:
    inner = RecordingEmbeddings()
    embeddings = KnowledgeEmbeddings(inner, batch_size=10)

    vector = await embeddings.aembed_query("工单分级")

    assert vector == [4.0, 1.0]
