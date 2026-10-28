"""DeepSeek（OpenAI 兼容）模型工厂，供出题与研究 Agent 复用。"""

from __future__ import annotations

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import Settings


def build_deepseek_http_client(settings: Settings) -> httpx.AsyncClient:
    proxy_url = settings.deepseek_proxy_url.strip()
    timeout = settings.deepseek_timeout_seconds
    if proxy_url:
        return httpx.AsyncClient(proxy=proxy_url, trust_env=False, timeout=timeout)
    return httpx.AsyncClient(trust_env=settings.deepseek_trust_env_proxy, timeout=timeout)


def build_deepseek_chat_model(
    settings: Settings,
    *,
    temperature: float,
    max_tokens: int,
) -> ChatOpenAI:
    thinking = "enabled" if settings.deepseek_thinking_enabled else "disabled"
    return ChatOpenAI(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=SecretStr(settings.deepseek_api_key),
        temperature=temperature,
        top_p=settings.llm_top_p,
        max_tokens=max_tokens,
        timeout=settings.deepseek_timeout_seconds,
        max_retries=0,
        extra_body={"thinking": {"type": thinking}},
        http_async_client=build_deepseek_http_client(settings),
        # 显式禁用内置 socket 选项，避免 langchain-openai 注入自定义 transport
        # 时产生“代理被屏蔽”的误导性告警；连接策略完全由 build_deepseek_http_client 决定。
        http_socket_options=(),
    )
