from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core.auth import create_access_token
from app.core.config import Settings
from app.main import create_app
from tests.conftest import (
    FakeProvider,
    FakeQuizRepository,
    FakeUserRepository,
    FakeWeChatClient,
    build_quiz_draft,
)

QUIZ_PAYLOAD = {
    "user_input": "我想学习 RAG，以及它和传统搜索的区别",
    "question_count": 5,
    "difficulty": "mixed",
}


def persistence_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=False,
        rate_limit_enabled=False,
        jwt_secret="unit-test-jwt-secret-long-enough",
        wechat_appid="wx_test_appid",
        wechat_app_secret="wx_test_secret",
    )


def build(settings: Settings | None = None) -> tuple[Any, FakeQuizRepository]:
    settings = settings or persistence_settings()
    quiz_repo = FakeQuizRepository()
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(),
        user_repo=FakeUserRepository(),
        quiz_repo=quiz_repo,
    )
    return app, quiz_repo


def auth_headers(user_id: int = 1, settings: Settings | None = None) -> dict[str, str]:
    settings = settings or persistence_settings()
    token = create_access_token(user_id=user_id, openid=f"openid-{user_id}", settings=settings)
    return {"Authorization": f"Bearer {token}"}


def generate_quiz(client: TestClient, headers: dict[str, str] | None = None) -> dict[str, Any]:
    response = client.post("/api/v1/quiz/generate", json=QUIZ_PAYLOAD, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def answer_all(quiz: dict[str, Any], correct: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, question in enumerate(quiz["questions"]):
        if index < correct:
            selected = list(question["answer"])
        else:
            selected = [option["key"] for option in question["options"] if option["key"] not in question["answer"]][:1]
        records.append(
            {
                "question_id": question["id"],
                "selected_answers": selected,
                "is_correct": True,
                "duration_ms": 2000,
            }
        )
    return records


def report_body(quiz: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "quiz_id": quiz["quiz_id"],
        "topic": quiz["title"],
        "questions": quiz["questions"],
        "answer_records": records,
    }


def test_quiz_is_persisted_when_token_present() -> None:
    app, quiz_repo = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        quiz = generate_quiz(client, auth_headers(user_id=7, settings=settings))

    saved = quiz_repo.quizzes.get(quiz["quiz_id"])
    assert saved is not None
    assert saved["user_id"] == 7
    assert saved["title"] == quiz["title"]
    assert len(saved["questions"]) == 5


def test_quiz_is_not_persisted_without_token() -> None:
    app, quiz_repo = build()

    with TestClient(app) as client:
        quiz = generate_quiz(client)

    assert quiz["quiz_id"] not in quiz_repo.quizzes


def test_report_persists_and_awards_xp_when_token_present() -> None:
    app, quiz_repo = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=3, settings=settings)
        quiz = generate_quiz(client, headers)
        records = answer_all(quiz, correct=4)
        response = client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["xp_gained"] == 18  # 10 + 4 * 2
    assert data["accuracy"] == 80
    assert quiz_repo.completed == [quiz["quiz_id"]]
    assert quiz_repo.xp_by_user[3] == 18


def test_report_awards_completion_xp_even_when_all_wrong() -> None:
    app, quiz_repo = build()
    settings = persistence_settings()

    with TestClient(app) as client:
        headers = auth_headers(user_id=4, settings=settings)
        quiz = generate_quiz(client, headers)
        records = answer_all(quiz, correct=0)
        response = client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)

    data = response.json()["data"]
    assert data["xp_gained"] == 10
    assert quiz_repo.xp_by_user[4] == 10


def test_report_does_not_persist_without_token() -> None:
    app, quiz_repo = build()

    with TestClient(app) as client:
        quiz = generate_quiz(client)
        records = answer_all(quiz, correct=5)
        response = client.post("/api/v1/report/generate", json=report_body(quiz, records))

    assert response.status_code == 200
    assert response.json()["data"]["xp_gained"] == 0
    assert quiz_repo.completed == []
    assert quiz_repo.xp_by_user == {}


def test_xp_gained_present_in_anonymous_response() -> None:
    app, _ = build()

    with TestClient(app) as client:
        quiz = generate_quiz(client)
        records = answer_all(quiz, correct=2)
        data = client.post("/api/v1/report/generate", json=report_body(quiz, records)).json()["data"]

    assert "xp_gained" in data
    assert isinstance(data["xp_gained"], int)


def test_quiz_generation_still_works_when_database_missing() -> None:
    settings = persistence_settings()
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(),
        user_repo=None,
        quiz_repo=None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/quiz/generate",
            json=QUIZ_PAYLOAD,
            headers=auth_headers(user_id=1, settings=settings),
        )

    assert response.status_code == 200
    assert response.json()["code"] == 0


def test_report_returns_ai_content_from_fake_provider() -> None:
    app, _ = build()

    with TestClient(app) as client:
        quiz = generate_quiz(client)
        records = answer_all(quiz, correct=5)
        data = client.post("/api/v1/report/generate", json=report_body(quiz, records)).json()["data"]

    assert data["three_line_summary"] == ["第一句总结", "第二句总结", "第三句总结"]
