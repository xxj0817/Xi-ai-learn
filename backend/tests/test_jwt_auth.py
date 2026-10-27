from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from app.core.auth import InvalidToken, create_access_token, decode_access_token
from app.core.config import Settings


def auth_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "mysql_enabled": False,
        "jwt_secret": "unit-test-secret-key-should-be-long-enough",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_token_roundtrip_keeps_user_id_and_openid() -> None:
    settings = auth_settings()

    token = create_access_token(user_id=7, openid="openid-abc", settings=settings)
    payload = decode_access_token(token, settings=settings)

    assert payload.user_id == 7
    assert payload.openid == "openid-abc"
    assert isinstance(payload.user_id, int)


def test_expired_token_is_rejected() -> None:
    settings = auth_settings()

    token = create_access_token(
        user_id=1,
        openid="openid-x",
        settings=settings,
        expires_delta=timedelta(seconds=-5),
    )

    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=settings)


def test_token_signed_with_other_secret_is_rejected() -> None:
    issuer = auth_settings(jwt_secret="a" * 40)
    verifier = auth_settings(jwt_secret="b" * 40)

    token = create_access_token(user_id=1, openid="openid-x", settings=issuer)

    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=verifier)


@pytest.mark.parametrize("bad_token", ["", "abc", "a.b.c", "Bearer", "null"])
def test_malformed_token_is_rejected(bad_token: str) -> None:
    settings = auth_settings()

    with pytest.raises(InvalidToken):
        decode_access_token(bad_token, settings=settings)


def test_token_without_subject_is_rejected() -> None:
    settings = auth_settings()
    token = jwt.encode({"openid": "openid-x"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=settings)


def test_token_without_openid_is_rejected() -> None:
    settings = auth_settings()
    token = jwt.encode({"sub": "3"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=settings)


def test_token_with_non_numeric_subject_is_rejected() -> None:
    settings = auth_settings()
    token = jwt.encode(
        {"sub": "not-a-number", "openid": "openid-x"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(InvalidToken):
        decode_access_token(token, settings=settings)
