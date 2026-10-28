"""题库领域模型。"""

from __future__ import annotations

from enum import Enum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class QuestionType(str, Enum):
    single = "single"
    multiple = "multiple"
    judge = "judge"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class SourceOrigin(str, Enum):
    user = "user"
    web = "web"


class GroundingStatus(str, Enum):
    grounded = "grounded"
    partial = "partial"
    model_only = "model_only"


class QuizSource(BaseModel):
    id: str
    title: str
    url: str = ""
    snippet: str = ""
    published_date: str | None = None
    origin: SourceOrigin = SourceOrigin.web


class QuizGrounding(BaseModel):
    status: GroundingStatus = GroundingStatus.model_only
    provider: str = "none"
    searched_at: str | None = None
    evidence_chars: int = 0


class QuestionOption(BaseModel):
    key: str
    text: str


class Question(BaseModel):
    id: str
    type: QuestionType
    stem: str
    options: list[QuestionOption]
    answer: list[str]
    explanation: str
    knowledge_point: str
    difficulty: Difficulty
    citations: list[str] = Field(default_factory=list)


class Quiz(BaseModel):
    quiz_id: str
    title: str
    summary: str
    source_type: str = "text"
    user_input: str
    questions: list[Question]
    sources: list[QuizSource] = Field(default_factory=list)
    grounding: QuizGrounding = Field(default_factory=QuizGrounding)


class QuizGenerateRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=4000)
    question_count: int = Field(default=5, ge=1, le=10)
    difficulty: Literal["mixed", "easy", "medium", "hard"] = "mixed"
    source_text: str = Field(default="", max_length=20_000)
    source_urls: list[str] = Field(default_factory=list)
    region: str | None = Field(default=None, max_length=32)
    locale: str | None = Field(default=None, max_length=32)

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw in value:
            url = str(raw).strip()
            if not url:
                raise ValueError("source_urls 不能包含空链接")
            if len(url) > 2048:
                raise ValueError("source_urls 中的链接不能超过 2048 个字符")
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("source_urls 只支持 http/https 链接")
            if url not in cleaned:
                cleaned.append(url)
        if len(cleaned) > 3:
            raise ValueError("source_urls 最多支持 3 个链接")
        return cleaned

