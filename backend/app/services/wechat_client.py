"""微信小程序登录客户端。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import WeChatLoginFailed, WeChatNotConfigured, WeChatUnavailable

logger = logging.getLogger(__name__)

# 这些错误码表示微信侧临时故障，可以提示用户重试
_TRANSIENT_ERRCODES = {-1, 45011}


@dataclass(frozen=True)
class WeChatSession:
    openid: str
    unionid: str | None = None


class HttpWeChatClient:
    """调用微信 jscode2session；不读取系统代理，避免残留代理导致失败。"""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport

    async def code2session(self, code: str) -> WeChatSession:
        if not self._settings.wechat_login_configured:
            raise WeChatNotConfigured()

        params = {
            "appid": self._settings.wechat_appid,
            "secret": self._settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.wechat_timeout_seconds,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.get(self._settings.wechat_code2session_url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("微信 code2session 请求失败：%s", type(exc).__name__)
            raise WeChatUnavailable() from exc

        if response.status_code >= 400:
            logger.warning("微信 code2session 返回 HTTP %s", response.status_code)
            raise WeChatUnavailable()

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            logger.warning("微信 code2session 返回非 JSON")
            raise WeChatUnavailable() from exc

        errcode = data.get("errcode")
        if errcode not in (None, 0):
            logger.info("微信 code2session 业务错误 errcode=%s", errcode)
            if errcode in _TRANSIENT_ERRCODES:
                raise WeChatUnavailable()
            raise WeChatLoginFailed()

        openid = str(data.get("openid") or "").strip()
        if not openid:
            logger.warning("微信 code2session 未返回 openid")
            raise WeChatLoginFailed()

        unionid = data.get("unionid")
        return WeChatSession(openid=openid, unionid=str(unionid) if unionid else None)


def build_wechat_client(settings: Settings) -> HttpWeChatClient:
    return HttpWeChatClient(settings)
