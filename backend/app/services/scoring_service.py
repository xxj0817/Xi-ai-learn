"""服务端权威判分与知识点聚合。"""

from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel

from app.core.exceptions import InvalidInput
from app.models.quiz import Question
from app.models.report import AnswerRecord


class QuestionResult(BaseModel):
    question_id: str
    stem: str
    knowledge_point: str
    correct_answer: list[str]
    selected_answers: list[str]
    is_correct: bool


class ScoreSummary(BaseModel):
    total: int
    correct: int
    accuracy: int
    mastered_points: list[str]
    weak_points: list[str]
    results: list[QuestionResult]


def build_score_summary(
    questions: Sequence[Question],
    records: Sequence[AnswerRecord],
) -> ScoreSummary:
    if not questions:
        raise InvalidInput("题库不能为空")

    question_map = {question.id: question for question in questions}
    if len(question_map) != len(questions):
        raise InvalidInput("题库中存在重复的题目 ID")

    record_ids = [record.question_id for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise InvalidInput("答题记录中存在重复题目")
    if set(record_ids) != set(question_map):
        missing = sorted(set(question_map) - set(record_ids))
        unknown = sorted(set(record_ids) - set(question_map))
        if missing:
            raise InvalidInput(f"答题记录不完整，缺少题目：{', '.join(missing)}")
        raise InvalidInput(f"答题记录包含未知题目：{', '.join(unknown)}")

    results: list[QuestionResult] = []
    mastered: list[str] = []
    weak: list[str] = []

    for record in records:
        question = question_map[record.question_id]
        option_keys = {option.key for option in question.options}
        selected = [str(item).strip().upper() for item in record.selected_answers if str(item).strip()]

        if not selected:
            raise InvalidInput(f"题目 {question.id} 未选择任何选项")
        invalid = [key for key in selected if key not in option_keys]
        if invalid:
            raise InvalidInput(f"题目 {question.id} 的答案不在选项中：{', '.join(invalid)}")

        is_correct = set(selected) == set(question.answer)
        results.append(
            QuestionResult(
                question_id=question.id,
                stem=question.stem,
                knowledge_point=question.knowledge_point,
                correct_answer=list(question.answer),
                selected_answers=selected,
                is_correct=is_correct,
            )
        )

        point = question.knowledge_point
        if is_correct and point not in mastered:
            mastered.append(point)
        if not is_correct and point not in weak:
            weak.append(point)

    total = len(questions)
    correct = sum(1 for result in results if result.is_correct)
    accuracy = int(math.floor(correct / total * 100 + 0.5))

    return ScoreSummary(
        total=total,
        correct=correct,
        accuracy=accuracy,
        mastered_points=mastered,
        weak_points=weak,
        results=results,
    )
