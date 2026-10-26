"""题库标准化与结构校验。"""

from __future__ import annotations

import logging

from app.core.exceptions import QuizFormatError
from app.llm.schemas import QuestionDraft, QuizDraft
from app.models.quiz import Difficulty, Question, QuestionOption, QuestionType, Quiz

logger = logging.getLogger(__name__)

_MAX_STEM_CHARS = 300
_MAX_EXPLANATION_CHARS = 1000
_MAX_OPTIONS = 6

_REQUIRED_TYPES = {QuestionType.single, QuestionType.multiple, QuestionType.judge}


def normalize_quiz(
    draft: QuizDraft | None,
    *,
    quiz_id: str,
    user_input: str,
    expected_count: int,
) -> Quiz:
    if draft is None:
        raise QuizFormatError("模型没有返回题库内容")

    if len(draft.questions) != expected_count:
        raise QuizFormatError(f"题目数量应为 {expected_count}，实际为 {len(draft.questions)}")

    questions = [_normalize_question(item, index) for index, item in enumerate(draft.questions, start=1)]

    if expected_count >= 5:
        present = {question.type for question in questions}
        missing = _REQUIRED_TYPES - present
        if missing:
            raise QuizFormatError(f"缺少题型：{', '.join(sorted(item.value for item in missing))}")

    title = draft.title.strip() or f"{user_input[:20]} 闯关"
    summary = draft.summary.strip() or "根据你的学习内容生成的闯关题库"

    return Quiz(
        quiz_id=quiz_id,
        title=title,
        summary=summary,
        source_type="text",
        user_input=user_input,
        questions=questions,
    )


def _normalize_question(draft: QuestionDraft, index: int) -> Question:
    stem = draft.stem.strip()
    if not stem:
        raise QuizFormatError(f"第 {index} 题题干为空")
    if len(stem) > _MAX_STEM_CHARS:
        raise QuizFormatError(f"第 {index} 题题干过长")

    if not 2 <= len(draft.options) <= _MAX_OPTIONS:
        raise QuizFormatError(f"第 {index} 题选项数量应为 2 到 {_MAX_OPTIONS} 个")

    options: list[QuestionOption] = []
    keys: list[str] = []
    for option in draft.options:
        key = str(option.key).strip().upper()
        text = option.text.strip()
        if not key or not text:
            raise QuizFormatError(f"第 {index} 题存在空选项")
        if key in keys:
            raise QuizFormatError(f"第 {index} 题选项 key 重复：{key}")
        keys.append(key)
        options.append(QuestionOption(key=key, text=text))

    if draft.type == QuestionType.judge and len(options) != 2:
        raise QuizFormatError(f"第 {index} 题判断题必须只有两个选项")

    answers: list[str] = []
    for raw in draft.answer:
        key = str(raw).strip().upper()
        if key and key not in answers:
            answers.append(key)
    if not answers:
        raise QuizFormatError(f"第 {index} 题缺少正确答案")
    unknown = [key for key in answers if key not in keys]
    if unknown:
        raise QuizFormatError(f"第 {index} 题答案不在选项中：{', '.join(unknown)}")

    if draft.type in {QuestionType.single, QuestionType.judge} and len(answers) != 1:
        raise QuizFormatError(f"第 {index} 题单选/判断题只能有一个正确答案")
    if draft.type == QuestionType.multiple and len(answers) < 2:
        raise QuizFormatError(f"第 {index} 题多选题至少需要两个正确答案")

    explanation = draft.explanation.strip()
    if not explanation:
        raise QuizFormatError(f"第 {index} 题缺少解析")
    if len(explanation) > _MAX_EXPLANATION_CHARS:
        explanation = explanation[:_MAX_EXPLANATION_CHARS]

    knowledge_point = draft.knowledge_point.strip() or "核心概念"
    difficulty = draft.difficulty if isinstance(draft.difficulty, Difficulty) else Difficulty.easy

    return Question(
        id=f"q{index}",
        type=draft.type,
        stem=stem,
        options=options,
        answer=answers,
        explanation=explanation,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
    )
