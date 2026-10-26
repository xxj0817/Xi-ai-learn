"""复盘报告领域模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.quiz import Question


class AnswerRecord(BaseModel):
    question_id: str
    selected_answers: list[str] = Field(default_factory=list)
    # 客户端上报值仅用于日志排查，报告正确率一律由服务端重新判定
    is_correct: bool | None = None
    duration_ms: int = Field(default=0, ge=0, le=600_000)


class ReportGenerateRequest(BaseModel):
    quiz_id: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=1, max_length=200)
    questions: list[Question] = Field(min_length=1, max_length=20)
    answer_records: list[AnswerRecord] = Field(min_length=1, max_length=20)


class Report(BaseModel):
    accuracy: int
    total: int
    correct: int
    mastered_points: list[str]
    weak_points: list[str]
    three_line_summary: list[str]
    advice: list[str]
    share_quote: str
