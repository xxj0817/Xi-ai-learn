"""闯关、答题记录与报告的数据访问。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Protocol

import aiomysql

from app.core.db import Database

logger = logging.getLogger(__name__)


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _parse_searched_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        logger.warning("JSON 字段解析失败，返回原始值")
        return value


class QuizRepositoryProtocol(Protocol):
    async def save_quiz(
        self,
        *,
        quiz_id: str,
        user_id: int,
        title: str,
        summary: str,
        user_input: str,
        questions: list[dict[str, Any]],
    ) -> None: ...

    async def save_grounding(
        self,
        *,
        quiz_id: str,
        user_id: int,
        sources: list[dict[str, Any]],
        grounding: dict[str, Any],
    ) -> None: ...

    async def complete_quiz(
        self,
        *,
        quiz_id: str,
        user_id: int,
        records: list[dict[str, Any]],
        total_questions: int,
        correct_count: int,
        accuracy: float,
        report: dict[str, Any],
        xp_gained: int,
    ) -> bool: ...

    async def save_progress(
        self,
        *,
        quiz_id: str,
        user_id: int,
        records: list[dict[str, Any]],
        answered_count: int,
    ) -> bool: ...

    async def list_in_progress(
        self, *, user_id: int, limit: int
    ) -> list[dict[str, Any]]: ...


class QuizRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def save_quiz(
        self,
        *,
        quiz_id: str,
        user_id: int,
        title: str,
        summary: str,
        user_input: str,
        questions: list[dict[str, Any]],
    ) -> None:
        async with self._db.pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.Cursor) as cursor:
                    await cursor.execute(
                        "INSERT INTO quiz_sessions "
                        "(quiz_id, user_id, title, summary, user_input, questions_json) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE "
                        "title = %s, summary = %s, user_input = %s, questions_json = %s",
                        (
                            quiz_id,
                            user_id,
                            title,
                            summary,
                            user_input,
                            _dumps(questions),
                            title,
                            summary,
                            user_input,
                            _dumps(questions),
                        ),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def save_grounding(
        self,
        *,
        quiz_id: str,
        user_id: int,
        sources: list[dict[str, Any]],
        grounding: dict[str, Any],
    ) -> None:
        status = str(grounding.get("status") or "model_only")
        provider = str(grounding.get("provider") or "none")
        searched_at = _parse_searched_at(grounding.get("searched_at"))
        async with self._db.pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.Cursor) as cursor:
                    await cursor.execute(
                        "INSERT INTO quiz_grounding "
                        "(quiz_id, user_id, sources_json, grounding_json, status, provider, searched_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s) AS incoming "
                        "ON DUPLICATE KEY UPDATE "
                        "sources_json = incoming.sources_json, "
                        "grounding_json = incoming.grounding_json, "
                        "status = incoming.status, "
                        "provider = incoming.provider, "
                        "searched_at = incoming.searched_at",
                        (
                            quiz_id,
                            user_id,
                            _dumps(sources),
                            _dumps(grounding),
                            status,
                            provider,
                            searched_at,
                        ),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def complete_quiz(
        self,
        *,
        quiz_id: str,
        user_id: int,
        records: list[dict[str, Any]],
        total_questions: int,
        correct_count: int,
        accuracy: float,
        report: dict[str, Any],
        xp_gained: int,
    ) -> bool:
        """写入答题记录与报告并累加经验值；返回本次是否为首次提交（幂等保护）。"""
        awarded = False
        async with self._db.pool.acquire() as conn:
            try:
                await conn.begin()
                async with conn.cursor(aiomysql.Cursor) as cursor:
                    await cursor.execute(
                        "INSERT INTO answer_records "
                        "(quiz_id, user_id, records_json, total_questions, correct_count, accuracy) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE quiz_id = quiz_id",
                        (quiz_id, user_id, _dumps(records), total_questions, correct_count, accuracy),
                    )
                    # MySQL 语义：1=新插入，0/2=已存在（本次不重复发放经验值）
                    inserted = cursor.rowcount == 1

                    if inserted:
                        await cursor.execute(
                            "INSERT INTO reports (quiz_id, user_id, report_json, xp_gained) "
                            "VALUES (%s, %s, %s, %s)",
                            (quiz_id, user_id, _dumps(report), xp_gained),
                        )
                        if xp_gained:
                            await cursor.execute(
                                "UPDATE users SET total_xp = total_xp + %s WHERE id = %s",
                                (xp_gained, user_id),
                            )
                        awarded = True

                    # 完成即清理残留进度，避免出现在「未完成关卡」中
                    await cursor.execute(
                        "DELETE FROM quiz_progress WHERE quiz_id = %s", (quiz_id,)
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
        return awarded

    async def get_quiz(self, quiz_id: str) -> dict[str, Any] | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT quiz_id, user_id, title, summary, user_input, questions_json, created_at "
                    "FROM quiz_sessions WHERE quiz_id = %s",
                    (quiz_id,),
                )
                row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "quiz_id": row[0],
            "user_id": int(row[1]),
            "title": row[2],
            "summary": row[3],
            "user_input": row[4],
            "questions": _loads(row[5]) or [],
            "created_at": row[6],
        }

    async def get_answer_records(self, quiz_id: str) -> list[dict[str, Any]] | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT records_json FROM answer_records WHERE quiz_id = %s",
                    (quiz_id,),
                )
                row = await cursor.fetchone()
        return None if row is None else (_loads(row[0]) or [])

    async def get_report(self, quiz_id: str) -> dict[str, Any] | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT report_json FROM reports WHERE quiz_id = %s",
                    (quiz_id,),
                )
                row = await cursor.fetchone()
        return None if row is None else _loads(row[0])

    async def get_profile_stats(self, user_id: int) -> dict[str, int]:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT COUNT(*), COALESCE(SUM(correct_count), 0), COALESCE(AVG(accuracy), 0) "
                    "FROM answer_records WHERE user_id = %s",
                    (user_id,),
                )
                row = await cursor.fetchone()

        quiz_count = int(row[0] or 0)
        correct_count = int(row[1] or 0)
        average_accuracy = int(round(float(row[2] or 0)))
        return {
            "quiz_count": quiz_count,
            "correct_count": correct_count,
            "average_accuracy": average_accuracy,
        }

    async def list_quizzes(
        self, *, user_id: int, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        offset = (page - 1) * page_size
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM answer_records WHERE user_id = %s",
                    (user_id,),
                )
                total = int((await cursor.fetchone())[0] or 0)

                await cursor.execute(
                    "SELECT a.quiz_id, COALESCE(s.title, ''), a.accuracy, a.total_questions, a.correct_count, a.created_at "
                    "FROM answer_records a "
                    "LEFT JOIN quiz_sessions s ON s.quiz_id = a.quiz_id "
                    "WHERE a.user_id = %s "
                    "ORDER BY a.created_at DESC, a.id DESC "
                    "LIMIT %s OFFSET %s",
                    (user_id, page_size, offset),
                )
                rows = await cursor.fetchall()

        items = [
            {
                "quiz_id": row[0],
                "title": row[1] or "未命名闯关",
                "accuracy": int(round(float(row[2] or 0))),
                "question_count": int(row[3] or 0),
                "correct_count": int(row[4] or 0),
                "created_at": row[5],
            }
            for row in rows
        ]
        return items, total

    async def save_progress(
        self,
        *,
        quiz_id: str,
        user_id: int,
        records: list[dict[str, Any]],
        answered_count: int,
    ) -> bool:
        """保存答题进度；返回 False 表示该闯关不属于当前用户。"""
        async with self._db.pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.Cursor) as cursor:
                    await cursor.execute(
                        "SELECT 1 FROM quiz_sessions WHERE quiz_id = %s AND user_id = %s",
                        (quiz_id, user_id),
                    )
                    if await cursor.fetchone() is None:
                        return False

                    await cursor.execute(
                        "INSERT INTO quiz_progress (quiz_id, user_id, records_json, answered_count) "
                        "VALUES (%s, %s, %s, %s) AS incoming "
                        "ON DUPLICATE KEY UPDATE "
                        "records_json = incoming.records_json, "
                        "answered_count = incoming.answered_count, "
                        "updated_at = CURRENT_TIMESTAMP",
                        (quiz_id, user_id, _dumps(records), answered_count),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
        return True

    async def get_progress(self, quiz_id: str) -> list[dict[str, Any]]:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT records_json FROM quiz_progress WHERE quiz_id = %s", (quiz_id,)
                )
                row = await cursor.fetchone()
        return [] if row is None else (_loads(row[0]) or [])

    async def list_in_progress(self, *, user_id: int, limit: int) -> list[dict[str, Any]]:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT s.quiz_id, s.title, JSON_LENGTH(s.questions_json), "
                    "COALESCE(p.answered_count, 0), COALESCE(p.updated_at, s.created_at) "
                    "FROM quiz_sessions s "
                    "LEFT JOIN answer_records a ON a.quiz_id = s.quiz_id "
                    "LEFT JOIN quiz_progress p ON p.quiz_id = s.quiz_id "
                    "WHERE s.user_id = %s AND a.id IS NULL "
                    "ORDER BY COALESCE(p.updated_at, s.created_at) DESC, s.id DESC "
                    "LIMIT %s",
                    (user_id, limit),
                )
                rows = await cursor.fetchall()

        return [
            {
                "quiz_id": row[0],
                "title": row[1] or "未命名闯关",
                "question_count": int(row[2] or 0),
                "answered_count": int(row[3] or 0),
                "updated_at": row[4],
            }
            for row in rows
        ]

    async def get_quiz_detail(self, *, quiz_id: str, user_id: int) -> dict[str, Any] | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    "SELECT quiz_id, title, summary, user_input, questions_json, created_at "
                    "FROM quiz_sessions WHERE quiz_id = %s AND user_id = %s",
                    (quiz_id, user_id),
                )
                row = await cursor.fetchone()
                await cursor.execute(
                    "SELECT sources_json, grounding_json FROM quiz_grounding "
                    "WHERE quiz_id = %s AND user_id = %s",
                    (quiz_id, user_id),
                )
                grounding_row = await cursor.fetchone()

        if row is None:
            return None

        records = await self.get_answer_records(quiz_id)
        report = await self.get_report(quiz_id)
        progress = await self.get_progress(quiz_id)

        return {
            "quiz_id": row[0],
            "title": row[1],
            "summary": row[2],
            "user_input": row[3],
            "questions": _loads(row[4]) or [],
            "created_at": row[5],
            "answer_records": records or [],
            "progress": progress,
            "status": "completed" if records else "in_progress",
            "report": report,
            "sources": (_loads(grounding_row[0]) or []) if grounding_row else [],
            "grounding": (_loads(grounding_row[1]) or {}) if grounding_row else {},
        }
