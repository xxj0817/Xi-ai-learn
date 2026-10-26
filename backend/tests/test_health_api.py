from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["status"] == "ok"
    assert body["data"]["provider"] == "mock"
    assert body["data"]["model"] == "deepseek-flash"


def test_unknown_route_returns_json_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/not-exists")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 4040
    assert body["data"] is None


def test_openapi_document_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/health" in paths
    assert "/api/v1/quiz/generate" in paths
    assert "/api/v1/report/generate" in paths
