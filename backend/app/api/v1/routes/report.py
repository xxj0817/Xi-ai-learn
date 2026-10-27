"""复盘报告生成接口。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.auth import get_optional_user
from app.models.common import ApiResponse, ok
from app.models.report import Report, ReportGenerateRequest
from app.services.report_service import ReportService

router = APIRouter()


@router.post("/report/generate", response_model=ApiResponse[Report])
async def generate_report(payload: ReportGenerateRequest, request: Request) -> ApiResponse[Report]:
    current_user = get_optional_user(request)
    service = ReportService(
        request.app.state.provider,
        getattr(request.app.state, "quiz_repo", None),
    )
    report = await service.generate(payload, user_id=current_user.user_id if current_user else None)
    return ok(report)
