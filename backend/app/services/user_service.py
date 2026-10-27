"""用户服务：微信登录、档案读写。"""

from __future__ import annotations

import logging

from app.core.auth import create_access_token
from app.core.config import Settings
from app.core.exceptions import ResourceNotFound, WeChatNotConfigured
from app.models.user import (
    LoginResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    UserPublic,
    UserRecord,
)
from app.repositories.quiz_repository import QuizRepositoryProtocol
from app.repositories.user_repository import UserRepositoryProtocol
from app.services.wechat_client import HttpWeChatClient

logger = logging.getLogger(__name__)

DEFAULT_NICKNAME = "学习者"
_EMPTY_STATS = {"quiz_count": 0, "correct_count": 0, "average_accuracy": 0}


def to_public(user: UserRecord) -> UserPublic:
    return UserPublic(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        total_xp=user.total_xp,
    )


class UserService:
    def __init__(
        self,
        settings: Settings,
        repository: UserRepositoryProtocol,
        wechat_client: HttpWeChatClient,
        quiz_repository: QuizRepositoryProtocol | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository
        self._wechat_client = wechat_client
        self._quiz_repository = quiz_repository

    async def login(self, code: str) -> LoginResponse:
        if not self._settings.wechat_login_configured:
            raise WeChatNotConfigured()

        session = await self._wechat_client.code2session(code)

        user = await self._repository.get_by_openid(session.openid)
        if user is None:
            user = await self._repository.create(openid=session.openid, nickname=DEFAULT_NICKNAME)
            logger.info("新用户注册 user_id=%s", user.id)

        token = create_access_token(user_id=user.id, openid=user.openid, settings=self._settings)
        return LoginResponse(token=token, user=to_public(user))

    async def get_profile(self, user_id: int) -> ProfileResponse:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise ResourceNotFound("用户不存在")

        stats = dict(_EMPTY_STATS)
        if self._quiz_repository is not None:
            try:
                stats = await self._quiz_repository.get_profile_stats(user_id)
            except Exception as exc:  # noqa: BLE001 - 统计失败不影响档案返回
                logger.warning("用户统计查询失败 user_id=%s error=%s", user_id, type(exc).__name__)

        return ProfileResponse(
            id=user.id,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            total_xp=user.total_xp,
            quiz_count=int(stats.get("quiz_count", 0)),
            correct_count=int(stats.get("correct_count", 0)),
            average_accuracy=int(stats.get("average_accuracy", 0)),
        )

    async def update_profile(self, user_id: int, payload: ProfileUpdateRequest) -> ProfileResponse:
        if payload.nickname is None and payload.avatar_url is None:
            return await self.get_profile(user_id)

        updated = await self._repository.update_profile(
            user_id=user_id,
            nickname=payload.nickname,
            avatar_url=payload.avatar_url,
        )
        if updated is None:
            raise ResourceNotFound("用户不存在")

        return await self.get_profile(user_id)
