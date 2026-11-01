"""文本切分：按语义边界递归切块，并保留可追溯的元数据。"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.exceptions import InvalidInput
from app.models.knowledge import KnowledgeSourceType

# 中英文混排场景下按「段落 → 换行 → 句号 → 空格」逐级降级切分
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", " ", ""]


def split_text(
    text: str,
    *,
    doc_id: str,
    title: str,
    source_type: KnowledgeSourceType,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    cleaned = (text or "").strip()
    if not cleaned:
        raise InvalidInput("文档内容为空，无法建立知识库")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SEPARATORS,
        add_start_index=True,
        keep_separator=True,
    )
    raw_chunks = splitter.create_documents(
        [cleaned],
        metadatas=[
            {
                "doc_id": doc_id,
                "title": title,
                "source_type": source_type.value,
            }
        ],
    )

    chunks: list[Document] = []
    for piece in raw_chunks:
        content = piece.page_content.strip()
        if not content:
            continue
        metadata = dict(piece.metadata)
        metadata["chunk_index"] = len(chunks)
        chunks.append(Document(page_content=content, metadata=metadata))

    if not chunks:
        raise InvalidInput("文档内容为空，无法建立知识库")
    return chunks
