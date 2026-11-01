from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings

from app.core.auth import create_access_token
from app.core.config import Settings
from app.knowledge.vector_store import ChromaKnowledgeStore
from app.main import create_app
from app.repositories.knowledge_repository import InMemoryKnowledgeRepository
from app.services.knowledge_service import KnowledgeService
from tests.conftest import FakeProvider


class BagOfCharsEmbeddings(Embeddings):
    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for char in text:
            vector[ord(char) % self._dim] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def build_settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
        "kb_upload_dir": str(tmp_path / "uploads"),
        "jwt_secret": "test-secret-for-knowledge-api-0123456789",
    }
    values.update(overrides)
    return Settings(**values)


def auth_headers(settings: Settings, user_id: int) -> dict[str, str]:
    token = create_access_token(
        user_id=user_id, openid=f"openid-{user_id}", settings=settings
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def knowledge_client(tmp_path: Path) -> Iterator[tuple[TestClient, Settings]]:
    settings = build_settings(tmp_path)
    service = KnowledgeService(
        settings,
        repository=InMemoryKnowledgeRepository(),
        vector_store=ChromaKnowledgeStore(
            persist_dir=tmp_path / "chroma",
            embeddings=BagOfCharsEmbeddings(),
        ),
        upload_root=tmp_path / "uploads",
    )
    app = create_app(
        settings=settings,
        provider=FakeProvider(),
        knowledge_service=service,
    )
    with TestClient(app) as client:
        yield client, settings


def upload_markdown(client: TestClient, headers: dict[str, str], name: str = "培训.md"):
    return client.post(
        "/api/v1/knowledge/documents",
        headers=headers,
        files={"file": (name, "# 客服培训\n\n退货政策：七天无理由退货。".encode(), "text/markdown")},
    )


def test_upload_requires_auth(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, _settings = knowledge_client

    response = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("a.md", b"# T\n\ncontent", "text/markdown")},
    )

    assert response.status_code == 401
    assert response.json()["code"] == 4010


def test_upload_document_success(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, settings = knowledge_client
    headers = auth_headers(settings, 1)

    response = upload_markdown(client, headers)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["doc_id"].startswith("doc_")
    assert data["source_type"] == "md"
    assert data["status"] == "ready"
    assert data["chunk_count"] >= 1
    assert data["title"] == "客服培训"


def test_upload_rejects_unsupported_type(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, settings = knowledge_client

    response = client.post(
        "/api/v1/knowledge/documents",
        headers=auth_headers(settings, 1),
        files={"file": ("video.mp4", b"binary", "video/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 4001


def test_upload_rejects_oversized_file(tmp_path: Path) -> None:
    settings = build_settings(tmp_path, kb_max_file_bytes=1024)
    service = KnowledgeService(
        settings,
        repository=InMemoryKnowledgeRepository(),
        vector_store=ChromaKnowledgeStore(
            persist_dir=tmp_path / "chroma",
            embeddings=BagOfCharsEmbeddings(),
        ),
        upload_root=tmp_path / "uploads",
    )
    app = create_app(settings=settings, provider=FakeProvider(), knowledge_service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/knowledge/documents",
            headers=auth_headers(settings, 1),
            files={"file": ("big.txt", b"a" * 4000, "text/plain")},
        )

    assert response.status_code == 400
    assert "文件过大" in response.json()["message"]


def test_text_upload_and_list(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, settings = knowledge_client
    headers = auth_headers(settings, 1)

    created = client.post(
        "/api/v1/knowledge/documents/text",
        headers=headers,
        json={"title": "内部 FAQ", "content": "工单分级：P0 线上不可用，P1 功能受损。"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["source_type"] == "txt"

    listed = client.get("/api/v1/knowledge/documents", headers=headers)

    assert listed.status_code == 200
    body = listed.json()["data"]
    assert body["total"] == 1
    assert body["enabled"] is True
    assert body["items"][0]["title"] == "内部 FAQ"


def test_list_is_scoped_to_user(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, settings = knowledge_client
    upload_markdown(client, auth_headers(settings, 1))

    other = client.get("/api/v1/knowledge/documents", headers=auth_headers(settings, 2))

    assert other.status_code == 200
    assert other.json()["data"]["total"] == 0


def test_delete_document(knowledge_client: tuple[TestClient, Settings]) -> None:
    client, settings = knowledge_client
    headers = auth_headers(settings, 1)
    doc_id = upload_markdown(client, headers).json()["data"]["doc_id"]

    deleted = client.delete(f"/api/v1/knowledge/documents/{doc_id}", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True
    remaining = client.get("/api/v1/knowledge/documents", headers=headers)
    assert remaining.json()["data"]["total"] == 0


def test_delete_unknown_document_returns_404(
    knowledge_client: tuple[TestClient, Settings],
) -> None:
    client, settings = knowledge_client

    response = client.delete(
        "/api/v1/knowledge/documents/doc_missing", headers=auth_headers(settings, 1)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 4041


def test_delete_other_users_document_returns_404(
    knowledge_client: tuple[TestClient, Settings],
) -> None:
    client, settings = knowledge_client
    doc_id = upload_markdown(client, auth_headers(settings, 1)).json()["data"]["doc_id"]

    response = client.delete(
        f"/api/v1/knowledge/documents/{doc_id}", headers=auth_headers(settings, 2)
    )

    assert response.status_code == 404


def test_unconfigured_knowledge_returns_503(tmp_path: Path) -> None:
    settings = build_settings(tmp_path, kb_enabled=False)
    app = create_app(settings=settings, provider=FakeProvider())

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/knowledge/documents", headers=auth_headers(settings, 1)
        )

    assert response.status_code == 503
    assert response.json()["code"] == 5031
