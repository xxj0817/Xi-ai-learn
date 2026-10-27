"""用户领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Any

_NICKNAME_MAX = 100
_AVATAR_MAX = 500


class UserRecord(BaseModel):
    """users 表一行。"""

    id: int
    openid: str
    nickname: str = "学习者"
    avatar_url: str = ""
    total_xp: int = 0


class UserPublic(BaseModel):
    """对外暴露的用户信息，不含 openid。"""

    id: int
    nickname: str
    avatar_url: str
    total_xp: int


class LoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("code 不能为空")
        return cleaned


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


class ProfileResponse(BaseModel):
    id: int
    nickname: str
    avatar_url: str
    total_xp: int
    quiz_count: int = 0
    correct_count: int = 0
    average_accuracy: int = 0


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=_NICKNAME_MAX)
    avatar_url: str | None = Field(default=None, max_length=_AVATAR_MAX)

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("昵称不能为空")
        return cleaned

    @field_validator("avatar_url")
    @classmethod
    def normalize_avatar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()


class QuizHistoryItem(BaseModel):
    quiz_id: str
    title: str
    accuracy: int
    question_count: int
    created_at: str


class QuizHistoryPage(BaseModel):
    items: list[QuizHistoryItem]
    total: int
    page: int
    page_size: int


class QuizDetail(BaseModel):
    quiz_id: str
    title: str
    summary: str = ""
    user_input: str = ""
    questions: list[Any] = Field(default_factory=list)
    answer_records: list[Any] = Field(default_factory=list)
    report: Any | None = None
    created_at: str = ""
