from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.core.db import Database, split_sql_statements
from tests.conftest import integration_mysql_settings

pytestmark = pytest.mark.integration

TEST_DATABASE = "xi_ai_learn_test"
EXPECTED_TABLES = {"users", "quiz_sessions", "answer_records", "reports"}


@pytest.fixture
async def database() -> AsyncIterator[Database]:
    settings = integration_mysql_settings(TEST_DATABASE)
    if settings is None:
        pytest.skip(".env 不存在，跳过 MySQL 集成测试")

    db = Database(settings)
    try:
        await db.connect()
    except Exception as exc:  # noqa: BLE001 - 本机无 MySQL 时跳过
        pytest.skip(f"MySQL 不可用，跳过集成测试：{type(exc).__name__}")

    yield db
    await db.close()


def test_split_statements_ignores_comments_and_blank_lines() -> None:
    script = """
    -- 这是注释
    CREATE TABLE a (id INT);

    -- 另一段注释
    CREATE TABLE b (id INT);
    """

    statements = split_sql_statements(script)

    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE a")
    assert statements[1].startswith("CREATE TABLE b")


async def test_ping_succeeds(database: Database) -> None:
    assert await database.ping() is True


async def test_migrations_create_all_tables(database: Database) -> None:
    async with database.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
                (TEST_DATABASE,),
            )
            rows = await cursor.fetchall()

    assert EXPECTED_TABLES.issubset({row[0] for row in rows})


async def test_unique_indexes_prevent_duplicate_quiz_rows(database: Database) -> None:
    result: dict[str, bool] = {}
    async with database.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            for table in ("answer_records", "reports"):
                await cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.statistics "
                    "WHERE table_schema = %s AND table_name = %s AND index_name = %s AND non_unique = 0",
                    (TEST_DATABASE, table, f"uk_{table}_quiz_id"),
                )
                result[table] = (await cursor.fetchone())[0] > 0

    assert result == {"answer_records": True, "reports": True}


async def test_utf8mb4_supports_chinese(database: Database) -> None:
    async with database.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("CREATE TEMPORARY TABLE tmp_utf8_check (v VARCHAR(50))")
            await cursor.execute("INSERT INTO tmp_utf8_check (v) VALUES (%s)", ("闯关学习🎮",))
            await cursor.execute("SELECT v FROM tmp_utf8_check")
            value = (await cursor.fetchone())[0]
        await conn.rollback()

    assert value == "闯关学习🎮"
