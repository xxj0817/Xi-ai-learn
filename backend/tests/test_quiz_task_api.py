from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import Settings
from app.core.exceptions import AIProviderError
from app.main import create_app
from app.repositories.quiz_task_repository import InMemoryQuizTaskRepository
from tests.conftest import FakeProvider


def task_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_input": "Harness Engineering 是什么",
        "question_count": 5,
        "difficulty": "mixed",
    }
    payload.update(overrides)
    return payload


def wait_task(
    client: TestClient, task_id: str, timeout: float = 5.0
) -> dict[str, Any]:
    deadline = time.time() + timeout
    latest: dict[str, Any] | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/quiz/tasks/{task_id}")
        assert response.status_code == 200, response.text
        latest = response.json()["data"]
        if latest["status"] in {"succeeded", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"任务未在预期时间内结束: {latest}")


def test_create_task_returns_immediately(client: TestClient) -> None:
    response = client.post("/api/v1/quiz/tasks", json=task_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["task_id"].startswith("task_")
    assert data["status"] == "pending"
    assert data["stage"] == "queued"
    assert data["progress"] == 0
    assert data["poll_interval_ms"] == 2000
    assert data["quiz"] is None


def test_polling_returns_finished_quiz(
    client: TestClient, provider: FakeProvider
) -> None:
    created = client.post("/api/v1/quiz/tasks", json=task_payload()).json()["data"]

    task = wait_task(client, created["task_id"])

    assert task["status"] == "succeeded"
    assert task["stage"] == "completed"
    assert task["progress"] == 100
    assert task["quiz_id"].startswith("quiz_")
    assert task["quiz"]["quiz_id"] == task["quiz_id"]
    assert len(task["quiz"]["questions"]) == 5
    assert task["quiz"]["user_input"] == "Harness Engineering 是什么"
    assert provider.quiz_calls[0]["question_count"] == 5


def test_invalid_payload_is_rejected_before_task_creation(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/quiz/tasks", json=task_payload(question_count=2)
    )

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 4001
    assert body["data"] is None


def test_unknown_task_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/quiz/tasks/task_not_exists")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 4041


def test_failed_task_exposes_error(settings: Settings) -> None:
    app = create_app(
        settings=settings,
        provider=FakeProvider(quiz_error=AIProviderError("模型服务不可用")),
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/quiz/tasks", json=task_payload()
        ).json()["data"]

        task = wait_task(client, created["task_id"])

    assert task["status"] == "failed"
    assert task["stage"] == "failed"
    assert task["quiz"] is None
    assert task["error"]["code"] == 4002
    assert task["error"]["message"] == "模型服务不可用"


def test_task_is_private_to_owner(settings: Settings) -> None:
    owner = create_access_token(user_id=101, openid="openid-101", settings=settings)
    stranger = create_access_token(user_id=202, openid="openid-202", settings=settings)
    app = create_app(settings=settings, provider=FakeProvider())

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/quiz/tasks",
            json=task_payload(),
            headers={"Authorization": f"Bearer {owner}"},
        ).json()["data"]

        forbidden = client.get(
            f"/api/v1/quiz/tasks/{created['task_id']}",
            headers={"Authorization": f"Bearer {stranger}"},
        )
        allowed = client.get(
            f"/api/v1/quiz/tasks/{created['task_id']}",
            headers={"Authorization": f"Bearer {owner}"},
        )

    assert forbidden.status_code == 404
    assert allowed.status_code == 200
    assert allowed.json()["data"]["task_id"] == created["task_id"]


def test_anonymous_task_can_be_polled_without_token(client: TestClient) -> None:
    created = client.post("/api/v1/quiz/tasks", json=task_payload()).json()["data"]

    response = client.get(f"/api/v1/quiz/tasks/{created['task_id']}")

    assert response.status_code == 200
    assert response.json()["data"]["task_id"] == created["task_id"]


def test_startup_marks_leftover_tasks_failed(settings: Settings) -> None:
    repository = InMemoryQuizTaskRepository()
    asyncio.run(
        repository.create(
            task_id="task_leftover",
            user_id=None,
            request={"user_input": "RAG"},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        quiz_task_repo=repository,
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/quiz/tasks/task_leftover")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "failed"
    assert data["stage"] == "failed"
    assert data["error"]["code"] == 5001


def test_task_polling_does_not_consume_rate_limit() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=False,
        rate_limit_enabled=True,
        rate_limit_per_minute=1,
    )
    app = create_app(settings=settings, provider=FakeProvider())

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/quiz/tasks", json=task_payload()
        ).json()["data"]

        polls = [
            client.get(f"/api/v1/quiz/tasks/{created['task_id']}")
            for _ in range(3)
        ]
        second_create = client.post("/api/v1/quiz/tasks", json=task_payload())

    assert [response.status_code for response in polls] == [200, 200, 200]
    assert second_create.status_code == 429
