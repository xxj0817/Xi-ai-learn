from __future__ import annotations

import pytest

from app.llm.prompt_builder import build_chat_prompt
from app.prompts.quiz_prompt import build_quiz_messages


def test_prompt_with_json_braces_renders_without_template_errors() -> None:
    messages = build_quiz_messages("RAG 入门", question_count=5, difficulty="mixed")

    prompt = build_chat_prompt(messages)
    value = prompt.invoke({})

    assert prompt.input_variables == []
    assert len(value.messages) == 2
    assert value.messages[0].type == "system"
    assert '"questions"' in value.messages[0].content


def test_user_input_braces_are_preserved() -> None:
    user_input = "帮我理解 {user_input} 和 JSON {示例} 的区别"
    messages = build_quiz_messages(user_input, question_count=5, difficulty="mixed")

    value = build_chat_prompt(messages).invoke({})

    assert user_input in value.messages[1].content


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_chat_prompt([("assistant", "hi")])
