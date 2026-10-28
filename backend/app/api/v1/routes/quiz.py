"""题库生成接口：同步出题 + 异步任务（创建 / 轮询）。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.auth import get_optional_user
from app.core.exceptions import ResourceNotFound
from app.models.common import ApiResponse, ok
from app.models.quiz import Quiz, QuizGenerateRequest
from app.models.quiz_task import QuizTask
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/quiz/generate", response_model=ApiResponse[Quiz])
async def generate_quiz(payload: QuizGenerateRequest, request: Request) -> ApiResponse[Quiz]:
    """同步出题，保留给脚本与旧客户端；交互流程请使用异步任务。"""
    current_user = get_optional_user(request)
    service = QuizService(
        request.app.state.settings,
        request.app.state.provider,
        getattr(request.app.state, "quiz_repo", None),
        getattr(request.app.state, "research_service", None),
    )
    quiz = await service.generate(
        payload,
        user_id=current_user.user_id if current_user else None,
        accept_language=request.headers.get("accept-language"),
    )
    return ok(quiz)


@router.post("/quiz/tasks", response_model=ApiResponse[QuizTask], status_code=202)
async def create_quiz_task(
    payload: QuizGenerateRequest, request: Request
) -> ApiResponse[QuizTask]:
    current_user = get_optional_user(request)
    task = await request.app.state.quiz_task_worker.submit(
        payload,
        user_id=current_user.user_id if current_user else None,
        accept_language=request.headers.get("accept-language"),
    )
    return ok(task)


@router.get("/quiz/tasks/{task_id}", response_model=ApiResponse[QuizTask])
async def get_quiz_task(task_id: str, request: Request) -> ApiResponse[QuizTask]:
    current_user = get_optional_user(request)
    task = await request.app.state.quiz_task_worker.get(
        task_id,
        user_id=current_user.user_id if current_user else None,
    )
    if task is None:
        raise ResourceNotFound("生成任务不存在或已过期")
    return ok(task)

