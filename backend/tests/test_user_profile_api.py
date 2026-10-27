from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import Settings
from app.main import create_app
from tests.conftest import (
    FakeProvider,
    FakeQuizRepository,
    FakeUserRepository,
    FakeWeChatClient,
)
from tests.test_quiz_persistence_api import (
    QUIZ_PAYLOAD,
    answer_all,
    auth_headers,
    generate_quiz,
    report_body,
)


def profile_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=False,
        rate_limit_enabled=False,
        jwt_secret="unit-test-jwt-secret-long-enough",
        wechat_appid="wx_test_appid",
        wechat_app_secret="wx_test_secret",
    )


def build(settings: Settings | None = None) -> tuple[Any, FakeQuizRepository, FakeUserRepository]:
    settings = settings or profile_settings()
    quiz_repo = FakeQuizRepository()
    user_repo = FakeUserRepository()
    quiz_repo._user_repository = user_repo
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-profile"),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )
    return app, quiz_repo, user_repo


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/user/login", json={"code": "code-profile"})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_profile_requires_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.get("/api/v1/user/profile")

    assert response.status_code == 401
    assert response.json()["code"] == 4010


def test_profile_rejects_invalid_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.get("/api/v1/user/profile", headers={"Authorization": "Bearer nope"})

    assert response.status_code == 401


def test_new_user_profile_has_zero_stats() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        data = client.get("/api/v1/user/profile", headers=headers).json()["data"]

    assert data["nickname"] == "学习者"
    assert data["total_xp"] == 0
    assert data["quiz_count"] == 0
    assert data["correct_count"] == 0
    assert data["average_accuracy"] == 0


def test_profile_reflects_quiz_activity() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        records = answer_all(quiz, correct=4)
        client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)

        data = client.get("/api/v1/user/profile", headers=headers).json()["data"]

    assert data["quiz_count"] == 1
    assert data["correct_count"] == 4
    assert data["average_accuracy"] == 80
    assert data["total_xp"] == 18


def test_profile_does_not_leak_openid() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        response = client.get("/api/v1/user/profile", headers=headers)

    assert "openid" not in response.text


def test_update_nickname_persists() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        updated = client.put("/api/v1/user/profile", json={"nickname": "  鱼皮同学  "}, headers=headers).json()["data"]
        fetched = client.get("/api/v1/user/profile", headers=headers).json()["data"]

    assert updated["nickname"] == "鱼皮同学"
    assert fetched["nickname"] == "鱼皮同学"


def test_update_avatar_url_persists() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        data = client.put(
            "/api/v1/user/profile",
            json={"avatar_url": "https://example.com/a.png"},
            headers=headers,
        ).json()["data"]

    assert data["avatar_url"] == "https://example.com/a.png"


def test_update_profile_with_no_fields_is_noop() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        response = client.put("/api/v1/user/profile", json={}, headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["nickname"] == "学习者"


def test_blank_nickname_is_rejected() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        response = client.put("/api/v1/user/profile", json={"nickname": "   "}, headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_too_long_nickname_is_rejected() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        response = client.put("/api/v1/user/profile", json={"nickname": "长" * 101}, headers=headers)

    assert response.status_code == 400


def test_update_profile_requires_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.put("/api/v1/user/profile", json={"nickname": "x"})

    assert response.status_code == 401


def test_newly_renamed_user_shows_in_login_response() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        client.put("/api/v1/user/profile", json={"nickname": "学习者A"}, headers=headers)
        again = client.post("/api/v1/user/login", json={"code": "code-profile"}).json()["data"]

    assert again["user"]["nickname"] == "学习者A"
