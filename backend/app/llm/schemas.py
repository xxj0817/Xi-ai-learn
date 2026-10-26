"""LLM 结构化输出 Schema（与对外 API 模型解耦）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.quiz import Difficulty, QuestionType

_TYPE_ALIASES = {
    "single": "single",
    "single_choice": "single",
    "single-choice": "single",
    "单选": "single",
    "单选题": "single",
    "multiple": "multiple",
    "multiple_choice": "multiple",
    "multiple-choice": "multiple",
    "多选": "multiple",
    "多选题": "multiple",
    "judge": "judge",
    "true_false": "judge",
    "true-false": "judge",
    "boolean": "judge",
    "判断": "judge",
    "判断题": "judge",
}


class QuestionOptionDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str
    text: str


class QuestionDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    type: QuestionType
    stem: str
    options: list[QuestionOptionDraft]
    answer: list[str]
    explanation: str = ""
    knowledge_point: str = ""
    difficulty: Difficulty = Difficulty.easy

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: Any) -> Any:
        if isinstance(value, str):
            return _TYPE_ALIASES.get(value.strip().lower(), value.strip().lower())
        return value

    @field_validator("answer", mode="before")
    @classmethod
    def coerce_answer(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]

    @field_validator("difficulty", mode="before")
    @classmethod
    def normalize_difficulty(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized if normalized in {"easy", "medium", "hard"} else "easy"
        return value


class QuizDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    summary: str = ""
    questions: list[QuestionDraft] = Field(default_factory=list)


class ReportDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    three_line_summary: list[str] = Field(default_factory=list)
    advice: list[str] = Field(default_factory=list)
    share_quote: str = ""
