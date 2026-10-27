"""用户表数据访问。"""

from __future__ import annotations

from typing import Protocol

import aiomysql

from app.core.db import Database
from app.models.user import UserRecord

_SELECT_COLUMNS = "id, openid, nickname, avatar_url, total_xp"


def _to_record(row: tuple[object, ...]) -> UserRecord:
    return UserRecord(
        id=int(row[0]),
        openid=str(row[1]),
        nickname=str(row[2]),
        avatar_url=str(row[3] or ""),
        total_xp=int(row[4] or 0),
    )


class UserRepositoryProtocol(Protocol):
    async def get_by_openid(self, openid: str) -> UserRecord | None: ...

    async def get_by_id(self, user_id: int) -> UserRecord | None: ...

    async def create(self, *, openid: str, nickname: str = "学习者") -> UserRecord: ...

    async def update_profile(
        self, *, user_id: int, nickname: str | None, avatar_url: str | None
    ) -> UserRecord | None: ...


class UserRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def get_by_openid(self, openid: str) -> UserRecord | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM users WHERE openid = %s",
                    (openid,),
                )
                row = await cursor.fetchone()
        return _to_record(row) if row else None

    async def get_by_id(self, user_id: int) -> UserRecord | None:
        async with self._db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.Cursor) as cursor:
                await cursor.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM users WHERE id = %s",
                    (user_id,),
                )
                row = await cursor.fetchone()
        return _to_record(row) if row else None

    async def create(self, *, openid: str, nickname: str = "学习者") -> UserRecord:
        async with self._db.pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.Cursor) as cursor:
                    await cursor.execute(
                        "INSERT INTO users (openid, nickname) VALUES (%s, %s) "
                        "ON DUPLICATE KEY UPDATE openid = openid",
                        (openid, nickname),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

        existing = await self.get_by_openid(openid)
        if existing is None:
            raise RuntimeError("创建用户后未能读回记录")
        return existing

    async def update_profile(
        self, *, user_id: int, nickname: str | None, avatar_url: str | None
    ) -> UserRecord | None:
        fields: list[str] = []
        params: list[object] = []
        if nickname is not None:
            fields.append("nickname = %s")
            params.append(nickname)
        if avatar_url is not None:
            fields.append("avatar_url = %s")
            params.append(avatar_url)

        if fields:
            params.append(user_id)
            async with self._db.pool.acquire() as conn:
                try:
                    async with conn.cursor(aiomysql.Cursor) as cursor:
                        await cursor.execute(
                            f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
                            tuple(params),
                        )
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise

        return await self.get_by_id(user_id)
