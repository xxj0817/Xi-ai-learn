from __future__ import annotations

import asyncio
from typing import Any, Sequence

import pytest

from app.core.config import Settings
from app.core.exceptions import InvalidInput
from app.knowledge.vector_store import ScoredChunk
from app.llm.schemas import ResearchBrief
from app.models.quiz import QuizGenerateRequest, QuizSource, SourceOrigin
from app.services.quiz_service import QuizService
from app.services.research_service import ResearchResult, ResearchService
from tests.conftest import FakeProvider, build_quiz_draft


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
        "web_search_enabled": False,
        "kb_top_k": 3,
        "kb_context_max_chars": 500,
    }
    values.update(overrides)
    return Settings(**values)


class FakeKnowledgeService:
    def __init__(self, chunks: list[ScoredChunk] | None = None) -> None:
        self._chunks = chunks if chunks is not None else [
            ScoredChunk(
                doc_id="doc_a",
                title="客服培训手册",
                chunk_index=0,
                content="退货政策：七天无理由退货，需要保留小票。",
                score=0.9,
            )
        ]
        self.calls: list[dict[str, Any]] = []
        self.doc_ids = ["doc_a"]

    async def search(
        self,
        *,
        user_id: int,
        query: str,
        doc_ids: Sequence[str] = (),
        top_k: int | None = None,
        max_chars: int | None = None,
    ) -> Any:
        self.calls.append({"user_id": user_id, "query": query, "doc_ids": list(doc_ids)})
        return type("Result", (), {"chunks": list(self._chunks)})()

    async def resolve_doc_ids(self, user_id: int, requested: Sequence[str]) -> list[str]:
        if requested and any(item not in self.doc_ids for item in requested):
            raise InvalidInput("知识库文档不存在或尚未就绪，请重新选择")
        return list(requested) or list(self.doc_ids)


class RecordingAgent:
    def __init__(self, brief: ResearchBrief | None = None) -> None:
        self._brief = brief or ResearchBrief(topic="")
        self.tool_names: list[str] = []
        self.calls = 0

    async def run(
        self,
        *,
        tools: Sequence[Any],
        user_input: str,
        urls: list[str],
        source_text: str,
        region: Any,
    ) -> ResearchBrief:
        self.calls += 1
        self.tool_names = [getattr(tool, "name", "") for tool in tools]
        return self._brief


def build_service(
    *,
    settings: Settings,
    knowledge: FakeKnowledgeService | None = None,
    agent: Any | None = None,
) -> ResearchService:
    return ResearchService(
        settings,
        agent=agent,
        knowledge_service=knowledge,
    )


async def test_knowledge_sources_are_used_without_agent() -> None:
    knowledge = FakeKnowledgeService()
    service = build_service(settings=make_settings(), knowledge=knowledge)

    result = await service.gather(
        user_input="退货政策是什么",
        user_id=1,
        knowledge_doc_ids=["doc_a"],
    )

    assert knowledge.calls
    assert result.provider == "knowledge"
    assert [source.origin for source in result.sources] == [SourceOrigin.knowledge]
    assert "退货" in result.sources[0].snippet
    assert result.searched_at is None


async def test_agent_receives_knowledge_tool() -> None:
    knowledge = FakeKnowledgeService()
    agent = RecordingAgent(ResearchBrief(topic="退货政策"))
    service = build_service(settings=make_settings(), knowledge=knowledge, agent=agent)

    result = await service.gather(
        user_input="退货政策是什么",
        user_id=1,
        knowledge_doc_ids=["doc_a"],
    )

    assert agent.calls == 1
    assert "knowledge_search" in agent.tool_names
    assert result.topic == "退货政策"
    assert result.provider == "knowledge"


async def test_agent_without_tool_calls_falls_back_to_knowledge() -> None:
    knowledge = FakeKnowledgeService()
    agent = RecordingAgent(ResearchBrief(topic="退货政策"))
    service = build_service(settings=make_settings(), knowledge=knowledge, agent=agent)

    result = await service.gather(
        user_input="退货政策是什么",
        user_id=1,
        knowledge_doc_ids=["doc_a"],
    )

    assert knowledge.calls, "Agent 未调用工具时应补一次确定性检索"
    assert result.sources
    assert result.mode == "fallback"


async def test_knowledge_scope_participates_in_cache_key() -> None:
    knowledge = FakeKnowledgeService()
    service = build_service(settings=make_settings(), knowledge=knowledge)

    await service.gather(user_input="退货政策", user_id=1, knowledge_doc_ids=["doc_a"])
    await service.gather(user_input="退货政策", user_id=1, knowledge_doc_ids=["doc_b"])

    assert len(knowledge.calls) == 2


async def test_no_knowledge_when_user_anonymous() -> None:
    knowledge = FakeKnowledgeService()
    service = build_service(settings=make_settings(), knowledge=knowledge)

    result = await service.gather(
        user_input="退货政策", user_id=None, knowledge_doc_ids=["doc_a"]
    )

    assert knowledge.calls == []
    assert result.sources == []


class FakeResearchWithKnowledge:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def gather(self, **kwargs: Any) -> ResearchResult:
        self.calls.append(kwargs)
        return ResearchResult(
            topic="退货政策",
            sources=[
                knowledge_source("S1", "客服培训手册", "", SourceOrigin.knowledge),
                knowledge_source("S2", "官网售后说明", "https://example.com", SourceOrigin.web),
            ],
            provider="mixed",
            searched_at="2026-11-01T00:00:00+00:00",
            evidence_chars=120,
            mode="agent",
        )


def knowledge_source(source_id: str, title: str, url: str, origin: SourceOrigin) -> QuizSource:
    return QuizSource(id=source_id, title=title, url=url, snippet="片段", origin=origin)


def grounded_draft(count: int = 5):
    draft = build_quiz_draft(count)
    for question in draft.questions:
        question.citations = ["S1"]
    return draft


def test_quiz_requires_login_for_knowledge_scope() -> None:
    service = QuizService(
        make_settings(),
        FakeProvider(quiz_drafts=[grounded_draft()]),
        research_service=FakeResearchWithKnowledge(),
        knowledge_service=FakeKnowledgeService(),
    )

    with pytest.raises(InvalidInput):
        asyncio.run(
            service.generate(
                QuizGenerateRequest(user_input="退货政策", knowledge_doc_ids=["doc_a"])
            )
        )


def test_quiz_passes_knowledge_scope_and_marks_source_type() -> None:
    research = FakeResearchWithKnowledge()
    knowledge = FakeKnowledgeService()
    service = QuizService(
        make_settings(),
        FakeProvider(quiz_drafts=[grounded_draft()]),
        research_service=research,
        knowledge_service=knowledge,
    )

    quiz = asyncio.run(
        service.generate(
            QuizGenerateRequest(user_input="退货政策", knowledge_doc_ids=["doc_a"]),
            user_id=1,
        )
    )

    assert research.calls[0]["knowledge_doc_ids"] == ["doc_a"]
    assert research.calls[0]["user_id"] == 1
    assert quiz.source_type == "mixed"
    assert {source.origin for source in quiz.sources} == {
        SourceOrigin.knowledge,
        SourceOrigin.web,
    }


def test_quiz_source_type_is_kb_when_only_knowledge_sources() -> None:
    class KnowledgeOnlyResearch:
        async def gather(self, **kwargs: Any) -> ResearchResult:
            return ResearchResult(
                topic="退货政策",
                sources=[knowledge_source("S1", "手册", "", SourceOrigin.knowledge)],
                provider="knowledge",
                searched_at=None,
                evidence_chars=50,
                mode="knowledge",
            )

    service = QuizService(
        make_settings(),
        FakeProvider(quiz_drafts=[grounded_draft()]),
        research_service=KnowledgeOnlyResearch(),
        knowledge_service=FakeKnowledgeService(),
    )

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="退货政策"), user_id=1)
    )

    assert quiz.source_type == "kb"
