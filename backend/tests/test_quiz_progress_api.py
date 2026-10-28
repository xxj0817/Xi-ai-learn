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
    generate_quiz,
    report_body,
)


def progress_settings() -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="mock",
        mysql_enabled=False,
        rate_limit_enabled=False,
        jwt_secret="unit-test-jwt-secret-long-enough",
        wechat_appid="wx_test_appid",
        wechat_app_secret="wx_test_secret",
    )


def build() -> tuple[Any, FakeQuizRepository, FakeUserRepository]:
    quiz_repo = FakeQuizRepository()
    user_repo = FakeUserRepository()
    quiz_repo._user_repository = user_repo
    app = create_app(
        settings=progress_settings(),
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-progress"),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )
    return app, quiz_repo, user_repo


def login(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/user/login", json={"code": "code-progress"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def progress_records(quiz: dict[str, Any], answered: int) -> list[dict[str, Any]]:
    return [
        {
            "question_id": question["id"],
            "selected": ["A"],
            "is_correct": False,
            "duration_ms": 1200,
        }
        for question in quiz["questions"][:answered]
    ]


def report_style_records(quiz: dict[str, Any], answered: int) -> list[dict[str, Any]]:
    """与报告接口一致：使用 selected_answers 字段。"""
    return [
        {
            "question_id": question["id"],
            "selected_answers": ["A", "B"],
            "is_correct": True,
            "duration_ms": 1000,
        }
        for question in quiz["questions"][:answered]
    ]


def test_in_progress_requires_token() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        response = client.get("/api/v1/user/quizzes/in-progress")

    assert response.status_code == 401
    assert response.json()["code"] == 4010


def test_generated_quiz_shows_up_as_in_progress() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)

        data = client.get("/api/v1/user/quizzes/in-progress", headers=headers).json()["data"]

    assert len(data["items"]) == 1
    assert data["items"][0]["quiz_id"] == quiz["quiz_id"]
    assert data["items"][0]["answered_count"] == 0
    assert data["items"][0]["question_count"] == len(quiz["questions"])


def test_progress_updates_answered_count() -> None:
    app, quiz_repo, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)

        response = client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 2)},
            headers=headers,
        )
        data = client.get("/api/v1/user/quizzes/in-progress", headers=headers).json()["data"]

    assert response.status_code == 200
    assert response.json()["data"]["answered_count"] == 2
    assert data["items"][0]["answered_count"] == 2


def test_progress_replaces_previous_records() -> None:
    app, quiz_repo, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 3)},
            headers=headers,
        )
        client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 1)},
            headers=headers,
        )
        data = client.get("/api/v1/user/quizzes/in-progress", headers=headers).json()["data"]

    assert data["items"][0]["answered_count"] == 1


def test_progress_records_are_visible_in_detail() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 2)},
            headers=headers,
        )
        detail = client.get(f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers).json()["data"]

    assert detail["status"] == "in_progress"
    assert len(detail["progress"]) == 2
    assert detail["progress"][0]["question_id"] == quiz["questions"][0]["id"]


def test_progress_requires_ownership() -> None:
    user_repo = FakeUserRepository()
    quiz_repo = FakeQuizRepository()
    quiz_repo._user_repository = user_repo
    settings = progress_settings()

    app_owner = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-owner"),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )
    app_other = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-other"),
        user_repo=user_repo,
        quiz_repo=quiz_repo,
    )

    with TestClient(app_owner) as owner_client, TestClient(app_other) as other_client:
        owner_headers = login(owner_client)
        other_headers = login(other_client)
        quiz = generate_quiz(owner_client, owner_headers)

        response = other_client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 1)},
            headers=other_headers,
        )

    assert response.status_code == 404
    assert response.json()["code"] == 4041


def test_progress_for_unknown_quiz_returns_not_found() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        response = client.put(
            "/api/v1/user/quizzes/quiz_missing/progress",
            json={"records": []},
            headers=headers,
        )

    assert response.status_code == 404
    assert response.json()["code"] == 4041


def test_completed_quiz_disappears_from_in_progress() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": progress_records(quiz, 2)},
            headers=headers,
        )
        records = answer_all(quiz, correct=4)
        client.post("/api/v1/report/generate", json=report_body(quiz, records), headers=headers)

        data = client.get("/api/v1/user/quizzes/in-progress", headers=headers).json()["data"]
        detail = client.get(f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers).json()["data"]

    assert data["items"] == []
    assert detail["status"] == "completed"
    assert detail["progress"] == []


def test_in_progress_only_returns_current_user_quizzes() -> None:
    repo_user_a = FakeUserRepository()
    quiz_repo = FakeQuizRepository()
    quiz_repo._user_repository = repo_user_a
    settings = progress_settings()

    app_a = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-a"),
        user_repo=repo_user_a,
        quiz_repo=quiz_repo,
    )
    app_b = create_app(
        settings=settings,
        provider=FakeProvider(),
        wechat_client=FakeWeChatClient(openid="openid-b"),
        user_repo=repo_user_a,
        quiz_repo=quiz_repo,
    )

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        headers_a = login(client_a)
        headers_b = login(client_b)
        generate_quiz(client_a, headers_a)

        data = client_b.get("/api/v1/user/quizzes/in-progress", headers=headers_b).json()["data"]

    assert data["items"] == []


def test_progress_accepts_selected_answers_field() -> None:
    """前端上报的字段名与报告接口一致（selected_answers），不能丢作答内容。"""
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": report_style_records(quiz, 1)},
            headers=headers,
        )
        detail = client.get(f"/api/v1/user/quizzes/{quiz['quiz_id']}", headers=headers).json()["data"]

    assert detail["progress"][0]["selected"] == ["A", "B"]
    assert detail["progress"][0]["is_correct"] is True


def test_progress_rejects_malformed_records() -> None:
    app, _, _ = build()

    with TestClient(app) as client:
        headers = login(client)
        quiz = generate_quiz(client, headers)
        response = client.put(
            f"/api/v1/user/quizzes/{quiz['quiz_id']}/progress",
            json={"records": [{"selected": ["A"]}]},
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["code"] == 4001
