from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import WeChatLoginFailed, WeChatNotConfigured, WeChatUnavailable
from app.services.wechat_client import HttpWeChatClient


def wechat_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "mysql_enabled": False,
        "wechat_appid": "wx_test_appid",
        "wechat_app_secret": "wx_test_secret",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def build_client(handler, **overrides: object) -> HttpWeChatClient:
    return HttpWeChatClient(wechat_settings(**overrides), transport=httpx.MockTransport(handler))


async def test_successful_code2session_returns_openid() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"openid": "openid-1", "session_key": "sk", "unionid": "u1"})

    session = await build_client(handler).code2session("code-123")

    assert session.openid == "openid-1"
    assert session.unionid == "u1"
    params = captured["params"]
    assert params["appid"] == "wx_test_appid"
    assert params["secret"] == "wx_test_secret"
    assert params["js_code"] == "code-123"
    assert params["grant_type"] == "authorization_code"


async def test_invalid_code_maps_to_login_failed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40029, "errmsg": "invalid code"})

    with pytest.raises(WeChatLoginFailed) as excinfo:
        await build_client(handler).code2session("bad-code")

    assert excinfo.value.code == 4004


async def test_used_code_maps_to_login_failed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40163, "errmsg": "code been used"})

    with pytest.raises(WeChatLoginFailed):
        await build_client(handler).code2session("used-code")


async def test_system_busy_maps_to_unavailable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": -1, "errmsg": "system error"})

    with pytest.raises(WeChatUnavailable) as excinfo:
        await build_client(handler).code2session("any-code")

    assert excinfo.value.code == 4005


async def test_missing_openid_maps_to_login_failed() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"session_key": "sk"})

    with pytest.raises(WeChatLoginFailed):
        await build_client(handler).code2session("any-code")


async def test_http_error_maps_to_unavailable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(WeChatUnavailable):
        await build_client(handler).code2session("any-code")


async def test_network_error_maps_to_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(WeChatUnavailable):
        await build_client(handler).code2session("any-code")


async def test_missing_credentials_raises_not_configured() -> None:
    client = build_client(lambda _: httpx.Response(200, json={}), wechat_app_secret="")

    with pytest.raises(WeChatNotConfigured) as excinfo:
        await client.code2session("any-code")

    assert excinfo.value.code == 5003


async def test_session_key_is_not_leaked_in_error_message() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 40029, "errmsg": "invalid code"})

    with pytest.raises(WeChatLoginFailed) as excinfo:
        await build_client(handler).code2session("bad")

    assert "invalid code" not in excinfo.value.message
