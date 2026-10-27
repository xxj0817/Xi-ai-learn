"""题库生成接口。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.auth import get_optional_user
from app.models.common import ApiResponse, ok
from app.models.quiz import Quiz, QuizGenerateRequest
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/quiz/generate", response_model=ApiResponse[Quiz])
async def generate_quiz(payload: QuizGenerateRequest, request: Request) -> ApiResponse[Quiz]:
    current_user = get_optional_user(request)
    service = QuizService(
        request.app.state.settings,
        request.app.state.provider,
        getattr(request.app.state, "quiz_repo", None),
    )
    quiz = await service.generate(payload, user_id=current_user.user_id if current_user else None)
    return ok(quiz)
