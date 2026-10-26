from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import FakeProvider

PAYLOAD = {
    "user_input": "我想学习 RAG，以及它和传统搜索的区别",
    "question_count": 5,
    "difficulty": "mixed",
}


def build_client(limit: int) -> TestClient:
    settings = Settings(
        _env_file=None,
        llm_provider="mock",
        rate_limit_enabled=True,
        rate_limit_per_minute=limit,
    )
    return TestClient(create_app(settings=settings, provider=FakeProvider()))


def test_rate_limit_blocks_requests_above_limit() -> None:
    with build_client(limit=1) as client:
        first = client.post("/api/v1/quiz/generate", json=PAYLOAD)
        second = client.post("/api/v1/quiz/generate", json=PAYLOAD)

    assert first.status_code == 200
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == 4290
    assert body["data"] is None


def test_health_endpoint_is_never_rate_limited() -> None:
    with build_client(limit=1) as client:
        for _ in range(3):
            assert client.get("/api/v1/health").status_code == 200
