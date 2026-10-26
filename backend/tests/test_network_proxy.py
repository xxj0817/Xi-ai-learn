from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.llm.deepseek_provider import DeepSeekProvider


def deepseek_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "deepseek",
        "deepseek_api_key": "sk-test",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_env_proxy_is_ignored_by_default() -> None:
    settings = deepseek_settings()

    assert settings.deepseek_trust_env_proxy is False
    assert settings.deepseek_proxy_url == ""


def test_http_client_does_not_trust_env_proxy_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:7897")
    model = DeepSeekProvider(deepseek_settings())._build_model(temperature=0.4, max_tokens=800)

    client = model.http_async_client

    assert isinstance(client, httpx.AsyncClient)
    assert client.trust_env is False
    assert not client._mounts


def test_env_proxy_can_be_enabled_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    model = DeepSeekProvider(deepseek_settings(deepseek_trust_env_proxy=True))._build_model(
        temperature=0.4, max_tokens=800
    )

    assert model.http_async_client.trust_env is True


def test_explicit_proxy_url_is_mounted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    model = DeepSeekProvider(
        deepseek_settings(deepseek_proxy_url="http://127.0.0.1:7890")
    )._build_model(temperature=0.4, max_tokens=800)

    client = model.http_async_client

    assert client.trust_env is False
    assert client._mounts


def test_model_build_emits_no_proxy_shadow_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7897")
    with caplog.at_level("WARNING", logger="langchain_openai.chat_models._client_utils"):
        model = DeepSeekProvider(deepseek_settings())._build_model(temperature=0.4, max_tokens=800)

    assert model.http_socket_options == ()
    assert "custom httpx transport" not in caplog.text
