"""用户领域模型。"""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field, field_validator
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
    progress: list[Any] = Field(default_factory=list)
    status: str = "completed"
    report: Any | None = None
    created_at: str = ""


class ProgressRecord(BaseModel):
    """单题答题进度，字段与前端 AnswerState 对齐。"""

    question_id: str = Field(min_length=1, max_length=64)
    # 前端上报答题记录时用 selected_answers（与报告接口一致），进度接口用 selected；
    # 两种字段名都接受，避免作答内容丢失。
    selected: list[str] = Field(
        default_factory=list,
        max_length=20,
        validation_alias=AliasChoices("selected", "selected_answers"),
    )
    is_correct: bool = False
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)


class QuizProgressRequest(BaseModel):
    records: list[ProgressRecord] = Field(default_factory=list, max_length=200)


class QuizProgressAck(BaseModel):
    quiz_id: str
    answered_count: int


class InProgressQuizItem(BaseModel):
    quiz_id: str
    title: str
    question_count: int
    answered_count: int
    updated_at: str


class InProgressQuizList(BaseModel):
    items: list[InProgressQuizItem] = Field(default_factory=list)


class AvatarUploadRequest(BaseModel):
    """小程序 chooseAvatar 拿到的本地文件按 base64 上传。"""

    data: str = Field(min_length=1, max_length=12_000_000)
    content_type: str = Field(default="image/png", max_length=64)
