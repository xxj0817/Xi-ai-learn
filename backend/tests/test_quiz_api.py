from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeProvider, build_question_draft, build_quiz_draft


def generate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "user_input": "我想学习 RAG，以及它和传统搜索的区别",
        "question_count": 5,
        "difficulty": "mixed",
    }
    payload.update(overrides)
    return payload


def test_generate_quiz_success(client: TestClient, provider: FakeProvider) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["quiz_id"].startswith("quiz_")
    assert data["source_type"] == "text"
    assert data["user_input"] == "我想学习 RAG，以及它和传统搜索的区别"
    assert len(data["questions"]) == 5
    assert [question["id"] for question in data["questions"]] == ["q1", "q2", "q3", "q4", "q5"]
    assert data["questions"][0]["options"][0].keys() == {"key", "text"}
    assert isinstance(data["questions"][0]["answer"], list)
    assert provider.quiz_calls[0]["question_count"] == 5
    assert provider.quiz_calls[0]["difficulty"] == "mixed"


def test_question_count_defaults_to_five(client: TestClient, provider: FakeProvider) -> None:
    payload = generate_payload()
    payload.pop("question_count")

    response = client.post("/api/v1/quiz/generate", json=payload)

    assert response.status_code == 200
    assert len(response.json()["data"]["questions"]) == 5
    assert provider.quiz_calls[0]["question_count"] == 5


def test_question_count_three_is_supported(client: TestClient) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload(question_count=3))

    assert response.status_code == 200
    assert len(response.json()["data"]["questions"]) == 3


def test_input_is_cleaned_before_returned(client: TestClient) -> None:
    response = client.post(
        "/api/v1/quiz/generate",
        json=generate_payload(user_input="  RAG\n\n  和   搜索  "),
    )

    assert response.status_code == 200
    assert response.json()["data"]["user_input"] == "RAG 和 搜索"


def test_too_short_input_is_rejected(client: TestClient, provider: FakeProvider) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload(user_input=" a "))

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == 4001
    assert body["data"] is None
    assert provider.quiz_calls == []


def test_too_long_input_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/quiz/generate",
        json=generate_payload(user_input="知" * 2001),
    )

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_invalid_question_count_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload(question_count=2))

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_invalid_difficulty_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload(difficulty="impossible"))

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_sensitive_input_is_rejected(client: TestClient, provider: FakeProvider) -> None:
    response = client.post("/api/v1/quiz/generate", json=generate_payload(user_input="教我赌博技巧"))

    assert response.status_code == 422
    assert response.json()["code"] == 4003
    assert provider.quiz_calls == []


def test_invalid_llm_output_is_retried_once(client: TestClient) -> None:
    invalid = build_quiz_draft(3)
    provider = FakeProvider(quiz_drafts=[invalid, build_quiz_draft(5)])
    app = client.app
    app.state.provider = provider

    response = client.post("/api/v1/quiz/generate", json=generate_payload())

    assert response.status_code == 200
    assert len(provider.quiz_calls) == 2
    assert provider.quiz_calls[0]["strict"] is False
    assert provider.quiz_calls[1]["strict"] is True


def test_repeated_invalid_llm_output_fails(client: TestClient) -> None:
    provider = FakeProvider(quiz_drafts=[build_quiz_draft(1), build_quiz_draft(2)])
    client.app.state.provider = provider

    response = client.post("/api/v1/quiz/generate", json=generate_payload())

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == 4002
    assert body["message"]
    assert len(provider.quiz_calls) == 2


def test_provider_exception_maps_to_generation_error(client: TestClient) -> None:
    provider = FakeProvider(quiz_error=RuntimeError("upstream timeout"))
    client.app.state.provider = provider

    response = client.post("/api/v1/quiz/generate", json=generate_payload())

    assert response.status_code == 502
    assert response.json()["code"] == 4002


def test_question_type_ratio_is_preserved(client: TestClient) -> None:
    draft = build_quiz_draft(5)
    draft.questions[0] = build_question_draft(1, "single")
    provider = FakeProvider(quiz_drafts=[draft])
    client.app.state.provider = provider

    response = client.post("/api/v1/quiz/generate", json=generate_payload())

    types = [question["type"] for question in response.json()["data"]["questions"]]
    assert types.count("multiple") == 1
    assert types.count("judge") == 1
