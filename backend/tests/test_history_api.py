from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.conftest import (
    FakeProvider,
    FakeQuizRepository,
    FakeUserRepository,
    FakeWeChatClient,
)
from tests.test_quiz_persistence_api import (
    answer_all,
    auth_headers,
    generate_quiz,
    persistence_settings,
    report_body,
)


def build(
    settings: Settings | None = None,
) -> tuple[Any, FakeQuizRepository, FakeUserRepository]:
    settings = settings or persistence_settings()
    quiz_repo = FakeQuizRepository()
    user_repo = FakeUserRepository()
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )
    return app, quiz_repo, user_repo


def seed_quizzes(client: TestClient, headers: dict[str, str], count: int, correct: int) -> list[str]:
    quiz_ids: list[str] = []
    for _ in range(count):
        quiz = generate_quiz(client, headers)
        records = answer_all(quiz, correct=correct)
        response = client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)
        assert response.status_code == 200
        quiz_ids.append(quiz["quiz_id"])
    return quiz_ids


def test_history_requires_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.get("/api/v1/user/quizzes")

    assert response.status_code == 401
    assert response.json()["code"] == 4010


def test_history_is_empty_for_new_user() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        data = client.get("/api/v1/user/quizzes", headers=auth_headers(user_id=1, settings=settings)).json()["data"]

    assert data == {"items": [], "total": 0, "page": 1, "page_size": 10}


def test_history_returns_completed_quizzes_newest_first() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        quiz_ids = seed_quizzes(client, headers, count=3, correct=4)
        data = client.get("/api/v1/user/quizzes", headers=headers).json()["data"]

    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["quiz_id"] == quiz_ids[-1]
    assert data["items"][0]["accuracy"] == 80
    assert data["items"][0]["question_count"] == 5
    assert data["items"][0]["title"]


def test_history_pagination() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        seed_quizzes(client, headers, count=3, correct=5)
        first = client.get("/api/v1/user/quizzes?page=1&page_size=2", headers=headers).json()["data"]
        second = client.get("/api/v1/user/quizzes?page=2&page_size=2", headers=headers).json()["data"]

    assert first["total"] == 3 and len(first["items"]) == 2
    assert second["total"] == 3 and len(second["items"]) == 1
    assert {item["quiz_id"] for item in first["items"]} & {item["quiz_id"] for item in second["items"]} == set()


def test_history_isolated_between_users() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers_a = auth_headers(user_id=1, settings=settings)
        seed_quizzes(client, headers_a, count=2, correct=5)
        data_b = client.get(
            "/api/v1/user/quizzes", headers=auth_headers(user_id=2, settings=settings)
        ).json()["data"]

    assert data_b["total"] == 0


def test_invalid_page_parameters_are_rejected() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        assert client.get("/api/v1/user/quizzes?page=0", headers=headers).status_code == 400
        assert client.get("/api/v1/user/quizzes?page_size=0", headers=headers).status_code == 400
        assert client.get("/api/v1/user/quizzes?page_size=101", headers=headers).status_code == 400


def test_quiz_detail_returns_questions_records_and_report() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        quiz = generate_quiz(client, headers)
        records = answer_all(quiz, correct=3)
        client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)
        data = client.get(f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers).json()["data"]

    assert data["quiz_id"] == quiz["quiz_id"]
    assert data["title"] == quiz["title"]
    assert len(data["questions"]) == 5
    assert len(data["answer_records"]) == 5
    assert data["report"]["accuracy"] == 60


def test_quiz_detail_404_for_unknown_id() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/user/quizzes/quiz_not_exists", headers=auth_headers(user_id=1, settings=settings)
        )

    assert response.status_code == 404
    assert response.json()["code"] == 4041


def test_quiz_detail_forbidden_for_other_user() -> None:
    app, _, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        owner_headers = auth_headers(user_id=1, settings=settings)
        quiz = generate_quiz(client, owner_headers)
        records = answer_all(quiz, correct=5)
        client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=owner_headers)

        response = client.get(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}",
            headers=auth_headers(user_id=2, settings=settings),
        )

    assert response.status_code == 404


def test_quiz_detail_requires_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.get("/api/v1/user/quizzes/quiz_1")

    assert response.status_code == 401


def test_quiz_detail_returns_sources_and_grounding_when_saved() -> None:
    app, quiz_repo, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        quiz = generate_quiz(client, headers)
        quiz_repo.grounding[quiz["quiz_id"]] = {
            "user_id": 1,
            "sources": [
                {
                    "id": "S1",
                    "title": "Harness Engineering",
                    "url": "https://example.com/harness",
                    "snippet": "AI Agent 工程实践",
                    "origin": "web",
                }
            ],
            "grounding": {
                "status": "grounded",
                "provider": "tavily",
                "searched_at": "2026-10-28T10:00:00+00:00",
                "evidence_chars": 12,
            },
        }

        data = client.get(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers
        ).json()["data"]

    assert data["sources"][0]["id"] == "S1"
    assert data["grounding"]["status"] == "grounded"
    assert data["grounding"]["provider"] == "tavily"


def test_quiz_detail_without_grounding_uses_defaults() -> None:
    app, quiz_repo, _ = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=1, settings=settings)
        quiz = generate_quiz(client, headers)
        quiz_repo.grounding.pop(quiz["quiz_id"], None)

        data = client.get(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers
        ).json()["data"]

    assert data["sources"] == []
    assert data["grounding"]["status"] == "model_only"
    assert data["grounding"]["provider"] == "none"

