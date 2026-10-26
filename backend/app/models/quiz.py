"""题库领域模型。"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class QuestionType(str, Enum):
    single = "single"
    multiple = "multiple"
    judge = "judge"


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


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


class Quiz(BaseModel):
    quiz_id: str
    title: str
    summary: str
    source_type: str = "text"
    user_input: str
    questions: list[Question]


class QuizGenerateRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=4000)
    question_count: int = Field(default=5, ge=1, le=10)
    difficulty: Literal["mixed", "easy", "medium", "hard"] = "mixed"
