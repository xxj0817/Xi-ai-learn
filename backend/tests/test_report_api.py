from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.llm.schemas import ReportDraft
from tests.conftest import FakeProvider


def generate_quiz(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/quiz/generate",
        json={
            "user_input": "我想学习 RAG，以及它和传统搜索的区别",
            "question_count": 5,
            "difficulty": "mixed",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]


def build_records(quiz: dict[str, Any], correct_ids: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for question in quiz["questions"]:
        if question["id"] in correct_ids:
            selected = list(question["answer"])
        else:
            selected = [option["key"] for option in question["options"] if option["key"] not in question["answer"]][:1]
        records.append(
            {
                "question_id": question["id"],
                "selected_answers": selected,
                "is_correct": True,
                "duration_ms": 3200,
            }
        )
    return records


def report_payload(quiz: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "quiz_id": quiz["quiz_id"],
        "topic": quiz["title"],
        "questions": quiz["questions"],
        "answer_records": records,
    }


def test_report_success(client: TestClient, provider: FakeProvider) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1", "q3"})

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["accuracy"] == 40
    assert data["correct"] == 2
    assert data["total"] == 5
    assert len(data["three_line_summary"]) == 3
    assert len(data["advice"]) >= 1
    assert data["share_quote"]
    assert data["mastered_points"] == ["知识点 1", "知识点 3"]
    assert data["weak_points"] == ["知识点 2", "知识点 4", "知识点 5"]
    assert provider.report_calls[0]["stats"]["accuracy"] == 40
    assert len(provider.report_calls[0]["question_results"]) == 5


def test_report_ignores_client_reported_correctness(client: TestClient, provider: FakeProvider) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, set())
    for record in records:
        record["is_correct"] = True

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["accuracy"] == 0
    assert data["correct"] == 0
    assert data["mastered_points"] == []


def test_report_all_correct_has_empty_weak_points(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {question["id"] for question in quiz["questions"]})

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["accuracy"] == 100
    assert data["weak_points"] == []


def test_report_missing_record_is_rejected(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})[:-1]

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_report_duplicate_record_is_rejected(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})
    records.append(records[0])

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_report_unknown_question_is_rejected(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})
    records[0]["question_id"] = "q404"

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_report_generation_failure_is_mapped(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})
    client.app.state.provider = FakeProvider(report_error=RuntimeError("llm down"))

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 502
    assert response.json()["code"] == 4002


def test_short_summary_is_padded_to_three_lines(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})
    client.app.state.provider = FakeProvider(
        report_draft=ReportDraft(
            three_line_summary=["只有一句"],
            advice=[],
            share_quote="",
        )
    )

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["three_line_summary"]) == 3
    assert all(line.strip() for line in data["three_line_summary"])
    assert data["advice"]
    assert data["share_quote"]


def test_summary_lines_are_cleaned(client: TestClient) -> None:
    quiz = generate_quiz(client)
    records = build_records(quiz, {"q1"})
    client.app.state.provider = FakeProvider(
        report_draft=ReportDraft(
            three_line_summary=["  第一句  ", "第二句", "第三句"],
            advice=["  建议  "],
            share_quote="  金句  ",
        )
    )

    response = client.post("/api/v1/report/generate", json=report_payload(quiz, records))

    data = response.json()["data"]
    assert data["three_line_summary"][0] == "第一句"
    assert data["advice"] == ["建议"]
    assert data["share_quote"] == "金句"
