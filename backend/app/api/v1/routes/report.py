"""复盘报告生成接口。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.common import ApiResponse, ok
from app.models.report import Report, ReportGenerateRequest
from app.services.report_service import ReportService

router = APIRouter()


@router.post("/report/generate", response_model=ApiResponse[Report])
async def generate_report(payload: ReportGenerateRequest, request: Request) -> ApiResponse[Report]:
    service = ReportService(request.app.state.provider)
    report = await service.generate(payload)
    return ok(report)
