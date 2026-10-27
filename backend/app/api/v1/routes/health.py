"""健康检查接口。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.models.common import ApiResponse, ok

router = APIRouter()


class HealthData(BaseModel):
    status: str
    provider: str
    model: str
    version: str
    database: str


@router.get("/health", response_model=ApiResponse[HealthData])
async def health(request: Request) -> ApiResponse[HealthData]:
    settings = request.app.state.settings
    database = getattr(request.app.state, "db", None)
    if database is None:
        database_status = "disabled" if not settings.mysql_enabled else "unavailable"
    else:
        database_status = "ok" if await database.ping() else "unavailable"

    return ok(
        HealthData(
            status="ok",
            provider=settings.llm_provider,
            model=settings.deepseek_model,
            version=settings.app_version,
            database=database_status,
        )
    )
