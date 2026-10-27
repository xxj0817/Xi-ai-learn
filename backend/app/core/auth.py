"""JWT 签发、解析与鉴权依赖。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import Unauthorized

logger = logging.getLogger(__name__)


class InvalidToken(Exception):
    """token 缺失、过期、签名不合法或字段不全。"""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    openid: str


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    openid: str


def create_access_token(
    *,
    user_id: int,
    openid: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(days=settings.jwt_expire_days))
    payload = {
        "sub": str(user_id),
        "openid": openid,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, *, settings: Settings) -> TokenPayload:
    candidate = (token or "").strip()
    if not candidate:
        raise InvalidToken("token 为空")

    try:
        payload = jwt.decode(candidate, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc

    subject = payload.get("sub")
    openid = payload.get("openid")
    if subject is None or openid is None:
        raise InvalidToken("token 缺少必要字段")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise InvalidToken("token 中的用户标识非法") from exc

    if not str(openid).strip():
        raise InvalidToken("token 中的 openid 为空")

    return TokenPayload(user_id=user_id, openid=str(openid))


def extract_bearer_token(request: Request) -> str | None:
    raw = request.headers.get("authorization") or request.headers.get("Authorization")
    if not raw or not raw.strip():
        return None

    value = raw.strip()
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    if len(parts) == 1:
        return parts[0].strip() or None
    return None


def get_optional_user(request: Request, settings: Settings | None = None) -> CurrentUser | None:
    """可选鉴权：token 缺失或无效时返回 None，不抛错。"""
    settings = settings or request.app.state.settings
    token = extract_bearer_token(request)
    if token is None:
        return None

    try:
        payload = decode_access_token(token, settings=settings)
    except InvalidToken as exc:
        logger.debug("可选鉴权忽略无效 token：%s", exc)
        return None

    return CurrentUser(user_id=payload.user_id, openid=payload.openid)


def require_user(request: Request, settings: Settings | None = None) -> CurrentUser:
    """强制鉴权：缺失或无效时抛 Unauthorized（4010）。"""
    user = get_optional_user(request, settings)
    if user is None:
        raise Unauthorized()
    return user
