from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import (
    FakeProvider,
    FakeQuizRepository,
    FakeUserRepository,
    FakeWeChatClient,
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 32
)


def avatar_settings(static_dir: Path) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=False,
        rate_limit_enabled=False,
        jwt_secret="unit-test-jwt-secret-long-enough",
        wechat_appid="wx_test_appid",
        wechat_app_secret="wx_test_secret",
        static_dir=str(static_dir),
    )


def build(static_dir: Path) -> tuple[Any, FakeUserRepository, Path]:
    user_repo = FakeUserRepository()
    quiz_repo = FakeQuizRepository()
    quiz_repo._user_repository = user_repo
    app = create_app(
        settings=avatar_settings(static_dir),
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-avatar"),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )
    return app, user_repo, static_dir


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/user/login", json={"code": "code-avatar"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def payload(raw: bytes = PNG_BYTES, content_type: str = "image/png") -> dict[str, str]:
    return {"data": base64.b64encode(raw).decode("ascii"), "content_type": content_type}


def test_avatar_upload_requires_token(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)

    with TestClient(app) as client:
        response = client.post("/api/v1/user/avatar", json=payload())

    assert response.status_code == 401
    assert response.json()["code"] == 4010


def test_avatar_upload_saves_file_and_updates_profile(tmp_path: Path) -> None:
    app, _, static_dir = build(tmp_path)

    with TestClient(app) as client:
        headers = login(client)
        response = client.post("/api/v1/user/avatar", json=payload(), headers=headers)
        profile = client.get("/api/v1/user/profile", headers=headers).json()["data"]

    assert response.status_code == 200, response.text
    avatar_url = response.json()["data"]["avatar_url"]
    assert avatar_url.startswith("http://testserver/static/avatars/")
    assert avatar_url.endswith(".png")
    assert profile["avatar_url"] == avatar_url

    saved = static_dir / "avatars" / avatar_url.rsplit("/", 1)[-1]
    assert saved.is_file()
    assert saved.read_bytes() == PNG_BYTES


def test_avatar_upload_serves_static_file(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)

    with TestClient(app) as client:
        headers = login(client)
        avatar_url = client.post("/api/v1/user/avatar", json=payload(), headers=headers).json()["data"][
            "avatar_url"
        ]
        fetched = client.get(avatar_url.replace("http://testserver", ""))

    assert fetched.status_code == 200
    assert fetched.content == PNG_BYTES


def test_avatar_upload_accepts_jpeg(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64

    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/user/avatar",
            json={"data": base64.b64encode(jpeg).decode("ascii"), "content_type": "image/jpeg"},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["data"]["avatar_url"].endswith(".jpg")


def test_avatar_upload_rejects_unsupported_type(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)

    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/user/avatar",
            json=payload(content_type="image/gif"),
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_avatar_upload_rejects_invalid_base64(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)

    with TestClient(app) as client:
        headers = login(client)
        response = client.post(
            "/api/v1/user/avatar",
            json={"data": "!!!!not-base64!!!!", "content_type": "image/png"},
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_avatar_upload_rejects_oversized_image(tmp_path: Path) -> None:
    app, _, _ = build(tmp_path)
    big = PNG_BYTES + b"\x00" * (3 * 1024 * 1024)

    with TestClient(app) as client:
        headers = login(client)
        response = client.post("/api/v1/user/avatar", json=payload(big), headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_avatar_upload_replaces_previous_file(tmp_path: Path) -> None:
    app, _, static_dir = build(tmp_path)

    with TestClient(app) as client:
        headers = login(client)
        first = client.post("/api/v1/user/avatar", json=payload(), headers=headers).json()["data"]["avatar_url"]
        second = client.post("/api/v1/user/avatar", json=payload(), headers=headers).json()["data"]["avatar_url"]

    first_file = static_dir / "avatars" / first.rsplit("/", 1)[-1]
    second_file = static_dir / "avatars" / second.rsplit("/", 1)[-1]
    assert second_file.is_file()
    assert not first_file.exists()
