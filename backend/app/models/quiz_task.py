"""异步出题任务模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.quiz import Quiz


class QuizTaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class QuizTaskStage(str, Enum):
    queued = "queued"
    researching = "researching"
    generating = "generating"
    validating = "validating"
    saving = "saving"
    completed = "completed"
    failed = "failed"


STAGE_PROGRESS: dict[QuizTaskStage, int] = {
    QuizTaskStage.queued: 0,
    QuizTaskStage.researching: 10,
    QuizTaskStage.generating: 35,
    QuizTaskStage.validating: 70,
    QuizTaskStage.saving: 90,
    QuizTaskStage.completed: 100,
    QuizTaskStage.failed: 0,
}


def stage_progress(stage: QuizTaskStage) -> int:
    return STAGE_PROGRESS.get(stage, 0)


class QuizTaskError(BaseModel):
    code: int = 5000
    message: str = "AI 出题失败，请稍后重试"


class QuizTask(BaseModel):
    task_id: str
    status: QuizTaskStatus
    stage: QuizTaskStage = QuizTaskStage.queued
    progress: int = Field(default=0, ge=0, le=100)
    quiz_id: str | None = None
    quiz: Quiz | None = None
    error: QuizTaskError | None = None
    poll_interval_ms: int = Field(default=2000, ge=500)
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in {QuizTaskStatus.succeeded, QuizTaskStatus.failed}
