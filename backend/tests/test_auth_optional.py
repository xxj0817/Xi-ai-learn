from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.auth import (
    CurrentUser,
    InvalidToken,
    create_access_token,
    get_optional_user,
    require_user,
)
from app.core.config import Settings
from app.core.exceptions import Unauthorized
from app.main import create_app
from tests.conftest import FakeProvider, FakeUserRepository


def auth_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "mysql_enabled": False,
        "rate_limit_enabled": False,
        "jwt_secret": "unit-test-jwt-secret-long-enough",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def make_request(headers: dict[str, str] | None = None) -> Any:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "headers": raw_headers, "method": "GET", "path": "/"})


def test_optional_user_returns_none_without_header() -> None:
    assert get_optional_user(make_request(), auth_settings()) is None


def test_optional_user_returns_none_for_empty_header() -> None:
    assert get_optional_user(make_request({"Authorization": "   "}), auth_settings()) is None


def test_optional_user_returns_none_for_invalid_token() -> None:
    request = make_request({"Authorization": "Bearer not-a-valid-token"})

    assert get_optional_user(request, auth_settings()) is None


def test_optional_user_parses_valid_bearer_token() -> None:
    settings = auth_settings()
    token = create_access_token(user_id=42, openid="openid-42", settings=settings)

    user = get_optional_user(make_request({"Authorization": f"Bearer {token}"}), settings)

    assert isinstance(user, CurrentUser)
    assert user.user_id == 42
    assert user.openid == "openid-42"


def test_optional_user_accepts_raw_token_without_bearer_prefix() -> None:
    settings = auth_settings()
    token = create_access_token(user_id=5, openid="openid-5", settings=settings)

    user = get_optional_user(make_request({"Authorization": token}), settings)

    assert user is not None
    assert user.user_id == 5


def test_optional_user_bearer_prefix_is_case_insensitive() -> None:
    settings = auth_settings()
    token = create_access_token(user_id=6, openid="openid-6", settings=settings)

    user = get_optional_user(make_request({"Authorization": f"bEaReR {token}"}), settings)

    assert user is not None
    assert user.user_id == 6


def test_require_user_raises_when_header_missing() -> None:
    with pytest.raises(Unauthorized) as excinfo:
        require_user(make_request(), auth_settings())

    assert excinfo.value.code == 4010


def test_require_user_raises_for_invalid_token() -> None:
    with pytest.raises(Unauthorized):
        require_user(make_request({"Authorization": "Bearer broken"}), auth_settings())


def test_require_user_returns_current_user() -> None:
    settings = auth_settings()
    token = create_access_token(user_id=9, openid="openid-9", settings=settings)

    user = require_user(make_request({"Authorization": f"Bearer {token}"}), settings)

    assert user.user_id == 9


def test_invalid_token_does_not_break_quiz_generation() -> None:
    settings = auth_settings()
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        user_repo=FakeUserRepository(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "RAG 和传统搜索的区别", "question_count": 5, "difficulty": "mixed"},
            headers={"Authorization": "Bearer totally-invalid"},
        )

    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_valid_token_does_not_break_quiz_generation() -> None:
    settings = auth_settings()
    token = create_access_token(user_id=1, openid="openid-1", settings=settings)
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        user_repo=FakeUserRepository(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/quiz/generate",
            json={"user_input": "RAG 和传统搜索的区别", "question_count": 5, "difficulty": "mixed"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200


def test_invalid_token_class_is_exception() -> None:
    assert issubclass(InvalidToken, Exception)
