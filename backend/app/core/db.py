"""MySQL 连接池、自动建库与迁移执行。"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import aiomysql

from app.core.config import Settings

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_LINE_COMMENT_RE = re.compile(r"^\s*--.*$", re.MULTILINE)

# 幂等迁移：列/索引已存在时继续执行后续语句
IGNORABLE_MIGRATION_ERRORS = {1060, 1061}


def split_sql_statements(script: str) -> list[str]:
    """按分号拆分 SQL 脚本，忽略空语句与整行注释。"""
    without_comments = _LINE_COMMENT_RE.sub("", script)
    return [statement.strip() for statement in without_comments.split(";") if statement.strip()]


class Database:
    """封装 aiomysql 连接池；未初始化时 available 为 False。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: aiomysql.Pool | None = None

    @property
    def available(self) -> bool:
        return self._pool is not None

    @property
    def pool(self) -> aiomysql.Pool:
        if self._pool is None:
            raise RuntimeError("数据库连接池尚未初始化")
        return self._pool

    async def connect(self) -> None:
        await self._ensure_database()
        self._pool = await aiomysql.create_pool(
            host=self._settings.mysql_host,
            port=self._settings.mysql_port,
            user=self._settings.mysql_user,
            password=self._settings.mysql_password,
            db=self._settings.mysql_database,
            charset="utf8mb4",
            # 自动提交：避免只读事务长期挂起导致连接复用时读到旧快照。
            # 需要原子性的多语句写入（如 complete_quiz）显式 begin/commit。
            autocommit=True,
            minsize=self._settings.mysql_pool_min_size,
            maxsize=self._settings.mysql_pool_max_size,
            pool_recycle=3600,
        )
        if self._settings.mysql_auto_migrate:
            await self.run_migrations()
        logger.info("MySQL 连接池已就绪 database=%s", self._settings.mysql_database)

    async def _ensure_database(self) -> None:
        conn = await aiomysql.connect(
            host=self._settings.mysql_host,
            port=self._settings.mysql_port,
            user=self._settings.mysql_user,
            password=self._settings.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("SET SESSION sql_notes = 0")
                await cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self._settings.mysql_database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
                await cursor.execute("SET SESSION sql_notes = 1")
        finally:
            conn.close()

    async def run_migrations(self) -> list[str]:
        executed: list[str] = []
        if not MIGRATIONS_DIR.is_dir():
            logger.warning("未找到 migrations 目录：%s", MIGRATIONS_DIR)
            return executed

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            script = path.read_text(encoding="utf-8")
            async with self.pool.acquire() as conn:
                try:
                    async with conn.cursor() as cursor:
                        # 表已存在属于正常情况，关闭 sql_notes 避免刷警告
                        await cursor.execute("SET SESSION sql_notes = 0")
                        for statement in split_sql_statements(script):
                            try:
                                await cursor.execute(statement)
                            except Exception as exc:  # noqa: BLE001 - 仅忽略幂等冲突
                                errno = exc.args[0] if exc.args else None
                                if errno not in IGNORABLE_MIGRATION_ERRORS:
                                    raise
                                logger.debug(
                                    "迁移语句已生效，跳过重复对象 errno=%s", errno
                                )
                        await cursor.execute("SET SESSION sql_notes = 1")
                    await conn.commit()
                except Exception:
                    await conn.rollback()
                    raise
            executed.append(path.name)
            logger.info("已执行迁移脚本 %s", path.name)
        return executed

    async def ping(self) -> bool:
        if self._pool is None:
            return False
        try:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
            return True
        except Exception as exc:  # noqa: BLE001 - 健康检查不应抛错
            logger.warning("数据库探活失败：%s", type(exc).__name__)
            return False

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            logger.info("MySQL 连接池已关闭")
