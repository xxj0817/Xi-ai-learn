"""题库生成接口。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.common import ApiResponse, ok
from app.models.quiz import Quiz, QuizGenerateRequest
from app.services.quiz_service import QuizService

router = APIRouter()


@router.post("/quiz/generate", response_model=ApiResponse[Quiz])
async def generate_quiz(payload: QuizGenerateRequest, request: Request) -> ApiResponse[Quiz]:
    service = QuizService(request.app.state.settings, request.app.state.provider)
    quiz = await service.generate(payload)
    return ok(quiz)
