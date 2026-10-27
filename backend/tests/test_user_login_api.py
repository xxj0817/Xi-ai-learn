from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import WeChatLoginFailed, WeChatUnavailable
from app.main import create_app
from tests.conftest import FakeProvider, FakeUserRepository, FakeWeChatClient


def login_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "mysql_enabled": False,
        "rate_limit_enabled": False,
        "wechat_appid": "wx_test_appid",
        "wechat_app_secret": "wx_test_secret",
        "jwt_secret": "unit-test-jwt-secret-long-enough",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def build_app(
    *,
    settings: Settings | None = None,
    repo: FakeUserRepository | None = None,
    wechat: FakeWeChatClient | None = None,
):
    settings = settings or login_settings()
    repo = repo if repo is not None else FakeUserRepository()
    wechat = wechat if wechat is not None else FakeWeChatClient(openid="openid_new")
    app = create_app(settings=settings, provider=FakeProvider(), wechat_client=wechat, user_repo=repo)
    return app, repo, wechat


def test_first_login_registers_user() -> None:
    app, repo, wechat = build_app()

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "code-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["token"]
    assert body["data"]["user"]["nickname"] == "学习者"
    assert body["data"]["user"]["avatar_url"] == ""
    assert body["data"]["user"]["total_xp"] == 0
    assert repo.created == ["openid_new"]
    assert wechat.calls == ["code-1"]
    assert "session_key" not in response.text


def test_second_login_reuses_existing_user() -> None:
    repo = FakeUserRepository()
    app, repo, _ = build_app(repo=repo)

    with TestClient(app) as client:
        first = client.post("/api/v1/user/login", json={"code": "code-1"}).json()
        second = client.post("/api/v1/user/login", json={"code": "code-2"}).json()

    assert first["data"]["user"]["id"] == second["data"]["user"]["id"]
    assert repo.created == ["openid_new"]


def test_different_openid_creates_different_user() -> None:
    wechat = FakeWeChatClient(openids_by_code={"code-a": "openid-a", "code-b": "openid-b"})
    app, repo, _ = build_app(wechat=wechat)

    with TestClient(app) as client:
        first = client.post("/api/v1/user/login", json={"code": "code-a"}).json()
        second = client.post("/api/v1/user/login", json={"code": "code-b"}).json()

    assert first["data"]["user"]["id"] != second["data"]["user"]["id"]
    assert sorted(repo.created) == ["openid-a", "openid-b"]


def test_login_returns_usable_token() -> None:
    app, _, _ = build_app()

    with TestClient(app) as client:
        token = client.post("/api/v1/user/login", json={"code": "code-1"}).json()["data"]["token"]
        profile = client.get("/api/v1/user/profile", headers={"Authorization": f"Bearer {token}"})

    assert profile.status_code == 200
    assert profile.json()["data"]["id"] == 1


def test_blank_code_is_rejected() -> None:
    app, _, wechat = build_app()

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "   "})

    assert response.status_code == 400
    assert response.json()["code"] == 4001
    assert wechat.calls == []


def test_missing_code_field_is_rejected() -> None:
    app, _, _ = build_app()

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={})

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_unconfigured_wechat_credentials_return_clear_error() -> None:
    app, repo, wechat = build_app(settings=login_settings(wechat_app_secret=""))

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "code-1"})

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == 5003
    assert "WECHAT_APP_SECRET" in body["message"]
    assert wechat.calls == []
    assert repo.created == []


def test_invalid_wechat_code_returns_login_failed() -> None:
    wechat = FakeWeChatClient(error=WeChatLoginFailed())
    app, repo, _ = build_app(wechat=wechat)

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "bad-code"})

    assert response.status_code == 400
    assert response.json()["code"] == 4004
    assert repo.created == []


def test_wechat_unavailable_returns_502() -> None:
    wechat = FakeWeChatClient(error=WeChatUnavailable())
    app, _, _ = build_app(wechat=wechat)

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "code-1"})

    assert response.status_code == 502
    assert response.json()["code"] == 4005


def test_database_unavailable_returns_503() -> None:
    settings = login_settings()
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid_new"),
        user_repo=None,
    )

    with TestClient(app) as client:
        response = client.post("/api/v1/user/login", json={"code": "code-1"})

    assert response.status_code == 503
    assert response.json()["code"] == 5030
