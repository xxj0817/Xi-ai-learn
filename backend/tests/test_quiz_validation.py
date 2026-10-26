from __future__ import annotations

import pytest

from app.llm.schemas import QuestionDraft, QuestionOptionDraft, QuizDraft
from app.services.quiz_normalizer import QuizFormatError, normalize_quiz


def option(key: str, text: str | None = None) -> QuestionOptionDraft:
    return QuestionOptionDraft(key=key, text=text or f"选项 {key}")


def make_question(
    question_type: str = "single",
    *,
    options: list[QuestionOptionDraft] | None = None,
    answer: list[str] | str | None = None,
    stem: str = "关于 RAG 的说法哪项正确？",
    explanation: str = "解析内容",
    knowledge_point: str = "RAG 基础",
    difficulty: str = "easy",
    question_id: str | None = None,
) -> QuestionDraft:
    if options is None:
        options = [option("A"), option("B"), option("C"), option("D")]
    if answer is None:
        answer = ["A"]
    return QuestionDraft.model_validate(
        {
            "id": question_id,
            "type": question_type,
            "stem": stem,
            "options": options,
            "answer": answer,
            "explanation": explanation,
            "knowledge_point": knowledge_point,
            "difficulty": difficulty,
        }
    )


def make_quiz(questions: list[QuestionDraft]) -> QuizDraft:
    return QuizDraft(title="RAG 入门闯关", summary="围绕 RAG 生成的题库", questions=questions)


def test_normalize_assigns_sequential_ids() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(), make_question(question_type="judge", options=[option("A"), option("B")])]),
        quiz_id="quiz_test",
        user_input="RAG 入门",
        expected_count=2,
    )

    assert quiz.quiz_id == "quiz_test"
    assert [question.id for question in quiz.questions] == ["q1", "q2"]
    assert quiz.questions[0].type == "single"
    assert quiz.questions[1].type == "judge"


def test_normalize_uppercases_option_keys_and_answers() -> None:
    quiz = normalize_quiz(
        make_quiz(
            [
                make_question(
                    options=[option("a"), option("b")],
                    answer=["a"],
                )
            ]
        ),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    question = quiz.questions[0]
    assert [item.key for item in question.options] == ["A", "B"]
    assert question.answer == ["A"]


def test_answer_as_string_is_coerced_to_list() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(answer="A")]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    assert quiz.questions[0].answer == ["A"]


def test_duplicate_question_ids_are_reassigned() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(question_id="q1"), make_question(question_id="q1")]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=2,
    )

    assert [question.id for question in quiz.questions] == ["q1", "q2"]


def test_single_choice_with_multiple_answers_is_rejected() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(answer=["A", "B"])]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_multiple_choice_requires_at_least_two_answers() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(question_type="multiple", answer=["A"])]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_multiple_choice_with_two_answers_is_accepted() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(question_type="multiple", answer=["A", "C"])]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    assert quiz.questions[0].answer == ["A", "C"]


def test_judge_question_requires_exactly_two_options() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(question_type="judge", options=[option("A"), option("B"), option("C")])]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_answer_outside_options_is_rejected() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(answer=["E"])]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_duplicate_option_keys_are_rejected() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(options=[option("A"), option("A")])]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_question_count_mismatch_is_rejected() -> None:
    with pytest.raises(QuizFormatError) as excinfo:
        normalize_quiz(
            make_quiz([make_question()]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=5,
        )

    assert "5" in str(excinfo.value)


def test_blank_stem_is_rejected() -> None:
    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz([make_question(stem="   ")]),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=1,
        )


def test_missing_knowledge_point_falls_back_to_default() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(knowledge_point="")]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    assert quiz.questions[0].knowledge_point == "核心概念"


def test_five_questions_require_all_three_question_types() -> None:
    questions = [make_question() for _ in range(5)]

    with pytest.raises(QuizFormatError):
        normalize_quiz(
            make_quiz(questions),
            quiz_id="quiz_test",
            user_input="RAG",
            expected_count=5,
        )


def test_five_questions_with_mixed_types_are_accepted() -> None:
    questions = [
        make_question(),
        make_question(),
        make_question(),
        make_question(question_type="multiple", answer=["A", "C"]),
        make_question(question_type="judge", options=[option("A"), option("B")]),
    ]

    quiz = normalize_quiz(
        make_quiz(questions),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=5,
    )

    assert [question.type for question in quiz.questions] == [
        "single",
        "single",
        "single",
        "multiple",
        "judge",
    ]


def test_difficulty_is_normalized() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(difficulty="MEDIUM")]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    assert quiz.questions[0].difficulty == "medium"


def test_unknown_difficulty_falls_back_to_easy() -> None:
    quiz = normalize_quiz(
        make_quiz([make_question(difficulty="impossible")]),
        quiz_id="quiz_test",
        user_input="RAG",
        expected_count=1,
    )

    assert quiz.questions[0].difficulty == "easy"
