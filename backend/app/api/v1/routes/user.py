"""用户相关接口：登录、档案。"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from app.core.auth import require_user
from app.core.exceptions import DatabaseUnavailable
from app.models.common import ApiResponse, ok
from app.models.user import (
    LoginRequest,
    LoginResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    QuizDetail,
    QuizHistoryPage,
)
from app.services.history_service import HistoryService
from app.services.user_service import UserService

router = APIRouter()


def _require_quiz_repository(request: Request):
    repository = getattr(request.app.state, "quiz_repo", None)
    if repository is None:
        raise DatabaseUnavailable()
    return repository


def _build_service(request: Request) -> UserService:
    repository = getattr(request.app.state, "user_repo", None)
    if repository is None:
        raise DatabaseUnavailable()
    return UserService(
        request.app.state.settings,
        repository,
        request.app.state.wechat_client,
        getattr(request.app.state, "quiz_repo", None),
    )


@router.post("/user/login", response_model=ApiResponse[LoginResponse])
async def login(payload: LoginRequest, request: Request) -> ApiResponse[LoginResponse]:
    service = _build_service(request)
    result = await service.login(payload.code)
    return ok(result)


@router.get("/user/profile", response_model=ApiResponse[ProfileResponse])
async def get_profile(request: Request) -> ApiResponse[ProfileResponse]:
    current_user = require_user(request)
    service = _build_service(request)
    return ok(await service.get_profile(current_user.user_id))


@router.put("/user/profile", response_model=ApiResponse[ProfileResponse])
async def update_profile(payload: ProfileUpdateRequest, request: Request) -> ApiResponse[ProfileResponse]:
    current_user = require_user(request)
    service = _build_service(request)
    return ok(await service.update_profile(current_user.user_id, payload))


@router.get("/user/quizzes", response_model=ApiResponse[QuizHistoryPage])
async def list_quizzes(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> ApiResponse[QuizHistoryPage]:
    current_user = require_user(request)
    service = HistoryService(_require_quiz_repository(request))
    return ok(await service.list_quizzes(user_id=current_user.user_id, page=page, page_size=page_size))


@router.get("/user/quizzes/{quiz_id}", response_model=ApiResponse[QuizDetail])
async def get_quiz_detail(quiz_id: str, request: Request) -> ApiResponse[QuizDetail]:
    current_user = require_user(request)
    service = HistoryService(_require_quiz_repository(request))
    return ok(await service.get_detail(user_id=current_user.user_id, quiz_id=quiz_id))
