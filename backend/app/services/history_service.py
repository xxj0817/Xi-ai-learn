"""闯关历史查询服务。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.core.exceptions import ResourceNotFound
from app.models.user import (
    InProgressQuizItem,
    InProgressQuizList,
    QuizDetail,
    QuizHistoryItem,
    QuizHistoryPage,
    QuizProgressAck,
    QuizProgressRequest,
)
from app.repositories.quiz_repository import QuizRepositoryProtocol

logger = logging.getLogger(__name__)


def _format_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


class HistoryService:
    def __init__(self, repository: QuizRepositoryProtocol) -> None:
        self._repository = repository

    async def list_quizzes(self, *, user_id: int, page: int, page_size: int) -> QuizHistoryPage:
        items, total = await self._repository.list_quizzes(
            user_id=user_id, page=page, page_size=page_size
        )
        return QuizHistoryPage(
            items=[
                QuizHistoryItem(
                    quiz_id=item["quiz_id"],
                    title=item["title"],
                    accuracy=int(item["accuracy"]),
                    question_count=int(item["question_count"]),
                    created_at=_format_time(item["created_at"]),
                )
                for item in items
            ],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_detail(self, *, user_id: int, quiz_id: str) -> QuizDetail:
        detail = await self._repository.get_quiz_detail(quiz_id=quiz_id, user_id=user_id)
        if detail is None:
            raise ResourceNotFound("闯关记录不存在")

        return QuizDetail(
            quiz_id=detail["quiz_id"],
            title=detail.get("title") or "未命名闯关",
            summary=detail.get("summary") or "",
            user_input=detail.get("user_input") or "",
            questions=detail.get("questions") or [],
            answer_records=detail.get("answer_records") or [],
            progress=detail.get("progress") or [],
            status=detail.get("status") or "completed",
            report=detail.get("report"),
            created_at=_format_time(detail.get("created_at")),
        )

    async def list_in_progress(self, *, user_id: int, limit: int = 10) -> InProgressQuizList:
        rows = await self._repository.list_in_progress(user_id=user_id, limit=limit)
        return InProgressQuizList(
            items=[
                InProgressQuizItem(
                    quiz_id=row["quiz_id"],
                    title=row["title"],
                    question_count=int(row["question_count"]),
                    answered_count=int(row["answered_count"]),
                    updated_at=_format_time(row.get("updated_at")),
                )
                for row in rows
            ]
        )

    async def save_progress(
        self, *, user_id: int, quiz_id: str, payload: QuizProgressRequest
    ) -> QuizProgressAck:
        records = [record.model_dump() for record in payload.records]
        saved = await self._repository.save_progress(
            quiz_id=quiz_id,
            user_id=user_id,
            records=records,
            answered_count=len(records),
        )
        if not saved:
            raise ResourceNotFound("闯关记录不存在")
        return QuizProgressAck(quiz_id=quiz_id, answered_count=len(records))
