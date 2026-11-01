"""把知识库检索包装成 Agent 可自主调用的工具。"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.search.source_collector import SourceCollector

logger = logging.getLogger(__name__)

KNOWLEDGE_TOOL_NAME = "knowledge_search"


class KnowledgeSearcherProtocol(Protocol):
    async def search(
        self,
        *,
        user_id: int,
        query: str,
        doc_ids: Sequence[str] = (),
        top_k: int | None = None,
        max_chars: int | None = None,
    ) -> object: ...


class KnowledgeSearchArgs(BaseModel):
    query: str = Field(
        description="要在用户私有知识库里检索的关键词或问题，尽量包含主题与关键术语"
    )


def build_knowledge_tool(
    service: KnowledgeSearcherProtocol,
    *,
    user_id: int,
    collector: SourceCollector,
    doc_ids: Sequence[str] = (),
    top_k: int = 5,
    max_chars: int = 4000,
) -> BaseTool:
    async def _search(query: str = "") -> dict[str, object]:
        question = (query or "").strip()[:300]
        if not question:
            return {"results": []}
        try:
            result = await service.search(
                user_id=user_id,
                query=question,
                doc_ids=doc_ids,
                top_k=top_k,
                max_chars=max_chars,
            )
        except Exception as exc:  # noqa: BLE001 - 工具失败交给 Agent 自行判断
            logger.warning("知识库工具调用失败 error=%s", type(exc).__name__)
            return {"error": type(exc).__name__}

        chunks = getattr(result, "chunks", []) or []
        return collector.record_knowledge(chunks)

    return StructuredTool.from_function(
        coroutine=_search,
        name=KNOWLEDGE_TOOL_NAME,
        description=(
            "在用户上传的私有知识库文档中做语义检索，返回最相关的原文片段。"
            "当问题涉及内部资料、企业培训、客服话术、私有题库等非公开知识时优先使用；"
            "query 请用一句具体的检索问题。"
        ),
        args_schema=KnowledgeSearchArgs,
    )
