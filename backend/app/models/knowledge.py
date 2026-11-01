"""知识库领域模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

# 支持的文档格式，与前端上传入口保持一致
SUPPORTED_EXTENSIONS = ("pdf", "docx", "md", "markdown", "txt")


class KnowledgeSourceType(str, Enum):
    pdf = "pdf"
    docx = "docx"
    md = "md"
    txt = "txt"


class KnowledgeDocumentStatus(str, Enum):
    ready = "ready"
    processing = "processing"
    failed = "failed"


class KnowledgeDocument(BaseModel):
    doc_id: str
    title: str
    source_type: KnowledgeSourceType
    size_bytes: int = 0
    chunk_count: int = 0
    status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.ready
    created_at: str = ""


class KnowledgeDocumentList(BaseModel):
    items: list[KnowledgeDocument] = Field(default_factory=list)
    total: int = 0
    enabled: bool = True


class KnowledgeDeleteResult(BaseModel):
    doc_id: str
    deleted: bool = True


class KnowledgeTextUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=200_000)

    @field_validator("title", "content")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("标题与正文不能为空")
        return cleaned


class KnowledgeSearchHit(BaseModel):
    doc_id: str
    title: str
    chunk_index: int
    content: str
    score: float = 0.0
