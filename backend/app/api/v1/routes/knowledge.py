"""知识库接口：上传、粘贴文本、列举、删除。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Request, UploadFile

from app.core.auth import require_user
from app.core.exceptions import InvalidInput, KnowledgeUnavailable
from app.models.common import ApiResponse, ok
from app.models.knowledge import (
    KnowledgeDeleteResult,
    KnowledgeDocument,
    KnowledgeDocumentList,
    KnowledgeTextUploadRequest,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


def _service(request: Request) -> KnowledgeService:
    service = getattr(request.app.state, "knowledge_service", None)
    if service is None:
        raise KnowledgeUnavailable("知识库未启用或未配置嵌入服务，请先在服务端配置 DASHSCOPE_API_KEY")
    return service


@router.post("/knowledge/documents", response_model=ApiResponse[KnowledgeDocument])
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="PDF / Word / Markdown / TXT 文档"),
) -> ApiResponse[KnowledgeDocument]:
    current_user = require_user(request)
    service = _service(request)
    settings = request.app.state.settings

    limit = settings.kb_max_file_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise InvalidInput(
            f"文件过大，请上传 {settings.kb_max_file_bytes / (1024 * 1024):.0f}MB 以内的文档"
        )
    try:
        document = await asyncio.wait_for(
            service.upload(
                user_id=current_user.user_id,
                filename=file.filename or "未命名文档.txt",
                data=data,
            ),
            timeout=settings.kb_upload_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise KnowledgeUnavailable("文档解析超时，请稍后重试或换一个更小的文件") from exc
    return ok(document)


@router.post("/knowledge/documents/text", response_model=ApiResponse[KnowledgeDocument])
async def upload_text(
    payload: KnowledgeTextUploadRequest, request: Request
) -> ApiResponse[KnowledgeDocument]:
    current_user = require_user(request)
    service = _service(request)
    settings = request.app.state.settings
    try:
        document = await asyncio.wait_for(
            service.add_text(
                user_id=current_user.user_id,
                title=payload.title,
                content=payload.content,
            ),
            timeout=settings.kb_upload_timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise KnowledgeUnavailable("文档处理超时，请稍后重试") from exc
    return ok(document)


@router.get("/knowledge/documents", response_model=ApiResponse[KnowledgeDocumentList])
async def list_documents(request: Request) -> ApiResponse[KnowledgeDocumentList]:
    current_user = require_user(request)
    service = _service(request)
    return ok(await service.list_documents(current_user.user_id))


@router.delete(
    "/knowledge/documents/{doc_id}", response_model=ApiResponse[KnowledgeDeleteResult]
)
async def delete_document(doc_id: str, request: Request) -> ApiResponse[KnowledgeDeleteResult]:
    current_user = require_user(request)
    service = _service(request)
    await service.delete(user_id=current_user.user_id, doc_id=doc_id)
    return ok(KnowledgeDeleteResult(doc_id=doc_id))
