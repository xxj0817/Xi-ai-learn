from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.llm.schemas import (
    QuestionDraft,
    QuestionOptionDraft,
    QuizDraft,
    ReportDraft,
)
from app.models.user import UserRecord
from app.services.wechat_client import WeChatSession
from app.main import create_app

TOPIC = "RAG 和传统搜索有什么区别"


def build_question_draft(index: int, question_type: str, topic: str = TOPIC) -> QuestionDraft:
    if question_type == "judge":
        options = [
            QuestionOptionDraft(key="A", text="正确"),
            QuestionOptionDraft(key="B", text="错误"),
        ]
        answer = ["A"]
    elif question_type == "multiple":
        options = [
            QuestionOptionDraft(key="A", text="检索增强生成"),
            QuestionOptionDraft(key="B", text="纯关键词匹配"),
            QuestionOptionDraft(key="C", text="向量召回"),
            QuestionOptionDraft(key="D", text="只能在离线环境使用"),
        ]
        answer = ["A", "C"]
    else:
        options = [
            QuestionOptionDraft(key="A", text="正确说法"),
            QuestionOptionDraft(key="B", text="错误说法一"),
            QuestionOptionDraft(key="C", text="错误说法二"),
            QuestionOptionDraft(key="D", text="错误说法三"),
        ]
        answer = ["A"]

    return QuestionDraft(
        type=question_type,
        stem=f"第 {index} 题：关于 {topic} 的说法，哪一项是成立的？",
        options=options,
        answer=answer,
        explanation=f"解析：第 {index} 题围绕 {topic} 的核心概念展开，注意区分检索与生成两个阶段。",
        knowledge_point=f"知识点 {index}",
        difficulty="easy",
    )


def question_type_plan(count: int) -> list[str]:
    plan = ["single", "single", "single", "multiple", "judge"]
    if count <= len(plan):
        return plan[:count]
    while len(plan) < count:
        plan.append("single")
    return plan


def build_quiz_draft(count: int = 5, topic: str = TOPIC) -> QuizDraft:
    questions = [
        build_question_draft(index, question_type, topic)
        for index, question_type in enumerate(question_type_plan(count), start=1)
    ]
    return QuizDraft(
        title=f"{topic[:12]} 闯关",
        summary=f"围绕 {topic} 生成的闯关题库",
        questions=questions,
    )


def build_report_draft() -> ReportDraft:
    return ReportDraft(
        three_line_summary=["第一句总结", "第二句总结", "第三句总结"],
        advice=["建议一", "建议二"],
        share_quote="把知识做成关卡，记忆会更深。",
    )


class FakeProvider:
    """Deterministic provider used by unit tests, records every call."""

    def __init__(
        self,
        quiz_drafts: list[QuizDraft] | None = None,
        report_draft: ReportDraft | None = None,
        quiz_error: Exception | None = None,
        report_error: Exception | None = None,
    ) -> None:
        self._quiz_drafts = list(quiz_drafts or [])
        self._report_draft = report_draft or build_report_draft()
        self._quiz_error = quiz_error
        self._report_error = report_error
        self.quiz_calls: list[dict[str, Any]] = []
        self.report_calls: list[dict[str, Any]] = []

    async def generate_quiz(
        self,
        *,
        topic: str,
        question_count: int,
        difficulty: str,
        strict: bool = False,
    ) -> QuizDraft:
        self.quiz_calls.append(
            {
                "topic": topic,
                "question_count": question_count,
                "difficulty": difficulty,
                "strict": strict,
            }
        )
        if self._quiz_error is not None:
            raise self._quiz_error
        if self._quiz_drafts:
            return self._quiz_drafts.pop(0)
        return build_quiz_draft(question_count, topic)

    async def generate_report(
        self,
        *,
        topic: str,
        quiz_summary: str,
        question_results: list[dict[str, Any]],
        stats: dict[str, Any],
        strict: bool = False,
    ) -> ReportDraft:
        self.report_calls.append(
            {
                "topic": topic,
                "quiz_summary": quiz_summary,
                "question_results": question_results,
                "stats": stats,
                "strict": strict,
            }
        )
        if self._report_error is not None:
            raise self._report_error
        return self._report_draft


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        rate_limit_enabled=False,
        mysql_enabled=False,
    )


class FakeWeChatClient:
    """可编程的微信登录客户端，避免单元测试依赖外网。"""

    def __init__(
        self,
        openid: str = "openid_default",
        unionid: str | None = None,
        error: Exception | None = None,
        openids_by_code: dict[str, str] | None = None,
    ) -> None:
        self._default_openid = openid
        self._unionid = unionid
        self._error = error
        self._openids_by_code = openids_by_code or {}
        self.calls: list[str] = []

    async def code2session(self, code: str) -> WeChatSession:
        self.calls.append(code)
        if self._error is not None:
            raise self._error
        return WeChatSession(
            openid=self._openids_by_code.get(code, self._default_openid),
            unionid=self._unionid,
        )


class FakeUserRepository:
    """内存版用户仓储，用于服务与接口层测试。"""
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {}
        self._next_id = 1
        self.created: list[str] = []

    async def get_by_openid(self, openid: str) -> UserRecord | None:
        return self.users.get(openid)

    async def get_by_id(self, user_id: int) -> UserRecord | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def create(self, *, openid: str, nickname: str = "学习者") -> UserRecord:
        user = UserRecord(id=self._next_id, openid=openid, nickname=nickname)
        self._next_id += 1
        self.users[openid] = user
        self.created.append(openid)
        return user

    async def update_profile(
        self, *, user_id: int, nickname: str | None, avatar_url: str | None
    ) -> UserRecord | None:
        user = await self.get_by_id(user_id)
        if user is None:
            return None
        updated = user.model_copy(
            update={
                "nickname": nickname if nickname is not None else user.nickname,
                "avatar_url": avatar_url if avatar_url is not None else user.avatar_url,
            }
        )
        self.users[updated.openid] = updated
        return updated


class FakeQuizRepository:
    """内存版闯关仓储，记录服务层调用便于断言。"""

    def __init__(self, user_repository: "FakeUserRepository | None" = None) -> None:
        self.quizzes: dict[str, dict[str, Any]] = {}
        self.completions: dict[str, dict[str, Any]] = {}
        self.completed: list[str] = []
        self.reports: dict[str, dict[str, Any]] = {}
        self.progress: dict[str, list[dict[str, Any]]] = {}
        self.xp_by_user: dict[int, int] = {}
        self._user_repository = user_repository

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
        self.quizzes[quiz_id] = {
            "quiz_id": quiz_id,
            "user_id": user_id,
            "title": title,
            "summary": summary,
            "user_input": user_input,
            "questions": questions,
        }

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
        if quiz_id in self.completions:
            return False
        self.completions[quiz_id] = {
            "quiz_id": quiz_id,
            "user_id": user_id,
            "records": records,
            "total_questions": total_questions,
            "correct_count": correct_count,
            "accuracy": accuracy,
        }
        self.completed.append(quiz_id)
        self.reports[quiz_id] = report
        self.progress.pop(quiz_id, None)
        self.xp_by_user[user_id] = self.xp_by_user.get(user_id, 0) + xp_gained
        if self._user_repository is not None:
            user = await self._user_repository.get_by_id(user_id)
            if user is not None:
                self._user_repository.users[user.openid] = user.model_copy(
                    update={"total_xp": user.total_xp + xp_gained}
                )
        return True

    async def get_profile_stats(self, user_id: int) -> dict[str, int]:
        rows = [item for item in self.completions.values() if item["user_id"] == user_id]
        if not rows:
            return {"quiz_count": 0, "correct_count": 0, "average_accuracy": 0}
        return {
            "quiz_count": len(rows),
            "correct_count": sum(int(item["correct_count"]) for item in rows),
            "average_accuracy": int(round(sum(float(item["accuracy"]) for item in rows) / len(rows))),
        }

    async def list_quizzes(
        self, *, user_id: int, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [item for item in self.completions.values() if item["user_id"] == user_id]
        rows.reverse()
        total = len(rows)
        start = (page - 1) * page_size
        sliced = rows[start : start + page_size]
        items = [
            {
                "quiz_id": item["quiz_id"],
                "title": self.quizzes.get(item["quiz_id"], {}).get("title", "未命名闯关"),
                "accuracy": int(round(float(item["accuracy"]))),
                "question_count": int(item["total_questions"]),
                "correct_count": int(item["correct_count"]),
                "created_at": "2026-10-27 10:00:00",
            }
            for item in sliced
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
        quiz = self.quizzes.get(quiz_id)
        if quiz is None or quiz["user_id"] != user_id:
            return False
        if quiz_id in self.completions:
            return False
        self.progress[quiz_id] = list(records)
        return True

    async def get_progress(self, quiz_id: str) -> list[dict[str, Any]]:
        return list(self.progress.get(quiz_id, []))

    async def list_in_progress(self, *, user_id: int, limit: int) -> list[dict[str, Any]]:
        rows = [
            {
                "quiz_id": quiz_id,
                "title": quiz["title"],
                "question_count": len(quiz["questions"]),
                "answered_count": len(self.progress.get(quiz_id, [])),
                "updated_at": "2026-10-27 11:00:00",
            }
            for quiz_id, quiz in self.quizzes.items()
            if quiz["user_id"] == user_id and quiz_id not in self.completions
        ]
        rows.reverse()
        return rows[:limit]

    async def get_quiz_detail(self, *, quiz_id: str, user_id: int) -> dict[str, Any] | None:
        quiz = self.quizzes.get(quiz_id)
        completion = self.completions.get(quiz_id)
        if quiz is None or quiz["user_id"] != user_id:
            return None
        return {
            "quiz_id": quiz_id,
            "title": quiz["title"],
            "summary": quiz["summary"],
            "user_input": quiz["user_input"],
            "questions": quiz["questions"],
            "created_at": "2026-10-27 10:00:00",
            "answer_records": completion["records"] if completion else [],
            "progress": [] if completion else list(self.progress.get(quiz_id, [])),
            "status": "completed" if completion else "in_progress",
            "report": self.reports.get(quiz_id),
        }


def integration_mysql_settings(database_name: str) -> Settings | None:
    """从 backend/.env 读取真实 MySQL 凭据，构造集成测试配置。"""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return None
    cfg = dotenv_values(env_path)
    return Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=True,
        mysql_host=cfg.get("MYSQL_HOST") or "127.0.0.1",
        mysql_port=int(cfg.get("MYSQL_PORT") or 3306),
        mysql_user=cfg.get("MYSQL_USER") or "root",
        mysql_password=cfg.get("MYSQL_PASSWORD") or "",
        mysql_database=database_name,
        mysql_auto_migrate=True,
    )


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


TRUNCATE_ORDER = ("answer_records", "reports", "quiz_sessions", "users")


@pytest.fixture
async def mysql_db() -> AsyncIterator[Any]:
    """真实 MySQL 测试库（xi_ai_learn_test），每个用例前清空业务表。"""
    from app.core.db import Database

    settings = integration_mysql_settings("xi_ai_learn_test")
    if settings is None:
        pytest.skip(".env 不存在，跳过 MySQL 集成测试")

    db = Database(settings)
    try:
        await db.connect()
    except Exception as exc:  # noqa: BLE001 - 本机无 MySQL 时跳过
        pytest.skip(f"MySQL 不可用，跳过集成测试：{type(exc).__name__}")

    async with db.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for table in TRUNCATE_ORDER:
                await cursor.execute(f"TRUNCATE TABLE {table}")
        await conn.commit()

    yield db
    await db.close()


@pytest.fixture
def client(settings: Settings, provider: FakeProvider) -> Iterator[TestClient]:
    app = create_app(settings=settings, provider=provider)
    with TestClient(app) as test_client:
        yield test_client
