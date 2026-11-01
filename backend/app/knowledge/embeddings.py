"""百炼 text-embedding-v4 嵌入封装。

百炼 OpenAI 兼容接口有两个硬约束：
1. 单次请求最多 10 条输入；
2. 不接受 OpenAI 的 base64 编码输入，必须关闭 check_embedding_ctx_length。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Sequence
from typing import TypeVar

import httpx
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from app.core.config import Settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _batched(items: Sequence[T], size: int) -> list[list[T]]:
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


class KnowledgeEmbeddings(Embeddings):
    """显式限制批大小的嵌入适配器，保证不超过服务端上限。"""

    def __init__(self, inner: Embeddings, *, batch_size: int = 10) -> None:
        self._inner = inner
        self._batch_size = max(1, batch_size)

    @property
    def inner(self) -> Embeddings:
        return self._inner

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for batch in _batched(texts, self._batch_size):
            vectors.extend(self._inner.embed_documents(batch))
        return vectors

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for batch in _batched(texts, self._batch_size):
            vectors.extend(await self._inner.aembed_documents(batch))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)

    async def aembed_query(self, text: str) -> list[float]:
        return await self._inner.aembed_query(text)


def _build_http_clients(settings: Settings) -> tuple[httpx.Client, httpx.AsyncClient]:
    proxy_url = settings.dashscope_proxy_url.strip()
    timeout = settings.embedding_timeout_seconds
    kwargs = (
        {"proxy": proxy_url, "trust_env": False}
        if proxy_url
        else {"trust_env": settings.dashscope_trust_env_proxy}
    )
    return (
        httpx.Client(timeout=timeout, **kwargs),
        httpx.AsyncClient(timeout=timeout, **kwargs),
    )


def build_embeddings(settings: Settings) -> KnowledgeEmbeddings:
    """构造知识库嵌入模型；未配置 Key 时抛错由调用方降级。"""
    api_key = settings.dashscope_api_key.strip()
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，知识库嵌入不可用")

    sync_client, async_client = _build_http_clients(settings)
    inner = OpenAIEmbeddings(
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        base_url=settings.dashscope_base_url,
        api_key=SecretStr(api_key),
        check_embedding_ctx_length=False,
        chunk_size=settings.embedding_batch_size,
        max_retries=0,
        timeout=settings.embedding_timeout_seconds,
        http_client=sync_client,
        http_async_client=async_client,
    )
    return KnowledgeEmbeddings(inner, batch_size=settings.embedding_batch_size)
