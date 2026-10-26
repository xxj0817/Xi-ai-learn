"""把已渲染的消息转换为 LangChain Prompt 模板。

注意：不能直接把 (role, content) 元组传给 ChatPromptTemplate.from_messages，
因为内容里的 JSON 花括号会被当成 f-string 变量解析。使用 BaseMessage 可原样保留。
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

_MESSAGE_TYPES = {
    "system": SystemMessage,
    "user": HumanMessage,
}


def build_chat_prompt(messages: list[tuple[str, str]]) -> ChatPromptTemplate:
    converted: list[BaseMessage] = []
    for role, content in messages:
        message_type = _MESSAGE_TYPES.get(role)
        if message_type is None:
            raise ValueError(f"不支持的消息角色：{role}")
        converted.append(message_type(content=content))
    return ChatPromptTemplate.from_messages(converted)
