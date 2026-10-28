from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.models.quiz import (
    GroundingStatus,
    QuizGenerateRequest,
    QuizSource,
    SourceOrigin,
)
from app.services.quiz_service import QuizService
from app.services.research_service import ResearchResult
from tests.conftest import FakeProvider, build_quiz_draft


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "mock",
        "rate_limit_enabled": False,
        "mysql_enabled": False,
        "llm_max_attempts": 2,
    }
    values.update(overrides)
    return Settings(**values)


def draft_with_citations(count: int = 5, citations: list[str] | None = None):
    draft = build_quiz_draft(count)
    for question in draft.questions:
        question.citations = list(citations if citations is not None else ["S1"])
    return draft


def web_source(source_id: str = "S1") -> QuizSource:
    return QuizSource(
        id=source_id,
        title="Harness Engineering",
        url="https://example.com/harness",
        snippet="Harness Engineering 是 AI Agent 工程实践。",
        origin=SourceOrigin.web,
    )


def user_source() -> QuizSource:
    return QuizSource(
        id="S1",
        title="用户资料",
        snippet="用户提供的资料正文",
        origin=SourceOrigin.user,
    )


class FakeResearchService:
    def __init__(
        self,
        *,
        topic: str = "Harness Engineering",
        sources: list[QuizSource] | None = None,
        provider: str = "tavily",
        searched_at: str | None = "2026-10-28T00:00:00+00:00",
        evidence_chars: int = 100,
        mode: str = "agent",
        error: Exception | None = None,
    ) -> None:
        self.result = ResearchResult(
            topic=topic,
            sources=sources or [],
            provider=provider,
            searched_at=searched_at,
            evidence_chars=evidence_chars,
            mode=mode,
        )
        self.error = error
        self.calls: list[dict] = []

    async def gather(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def test_grounded_quiz_uses_research_topic_and_sources() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(sources=[web_source()])
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert quiz.source_type == "web"
    assert len(quiz.sources) == 1
    assert quiz.sources[0].id == "S1"
    assert quiz.grounding.status == GroundingStatus.grounded
    assert quiz.grounding.provider == "tavily"
    assert quiz.grounding.evidence_chars == 100
    assert quiz.grounding.searched_at == "2026-10-28T00:00:00+00:00"
    assert all(question.citations == ["S1"] for question in quiz.questions)
    assert provider.quiz_calls[0]["topic"] == "Harness Engineering"
    assert provider.quiz_calls[0]["sources"] == ["S1"]


def test_url_input_uses_research_topic() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(topic="网页主题", sources=[web_source()])
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="https://example.com/harness"))
    )

    assert provider.quiz_calls[0]["topic"] == "网页主题"
    assert quiz.user_input == "https://example.com/harness"


def test_missing_citations_retries_with_strict_prompt() -> None:
    provider = FakeProvider(
        quiz_drafts=[
            draft_with_citations(citations=[]),
            draft_with_citations(citations=["S1"]),
        ]
    )
    research = FakeResearchService(sources=[web_source()])
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert len(provider.quiz_calls) == 2
    assert provider.quiz_calls[0]["strict"] is False
    assert provider.quiz_calls[1]["strict"] is True
    assert quiz.grounding.status == GroundingStatus.grounded


def test_partial_after_citation_retry_exhausted() -> None:
    provider = FakeProvider(
        quiz_drafts=[
            draft_with_citations(citations=[]),
            draft_with_citations(citations=[]),
        ]
    )
    research = FakeResearchService(sources=[web_source()])
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert len(provider.quiz_calls) == 2
    assert quiz.grounding.status == GroundingStatus.partial
    assert all(question.citations == [] for question in quiz.questions)


def test_partial_falls_back_to_first_valid_draft_when_retry_is_malformed() -> None:
    provider = FakeProvider(
        quiz_drafts=[
            draft_with_citations(citations=[]),
            build_quiz_draft(3),
        ]
    )
    research = FakeResearchService(sources=[web_source()])
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert len(provider.quiz_calls) == 2
    assert quiz.grounding.status == GroundingStatus.partial
    assert len(quiz.questions) == 5
    assert all(question.citations == [] for question in quiz.questions)


def test_model_only_when_research_has_no_sources() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(
        topic="Harness Engineering",
        sources=[],
        provider="none",
        searched_at=None,
        evidence_chars=0,
        mode="none",
    )
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert quiz.source_type == "text"
    assert quiz.grounding.status == GroundingStatus.model_only
    assert quiz.grounding.provider == "none"
    assert all(question.citations == [] for question in quiz.questions)


def test_user_source_type() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(
        sources=[user_source()],
        provider="user",
        searched_at=None,
        mode="user_only",
    )
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(service.generate(QuizGenerateRequest(user_input="测试主题")))

    assert quiz.source_type == "user"
    assert quiz.grounding.status == GroundingStatus.grounded


def test_mixed_source_type() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(
        sources=[user_source(), web_source("S2")],
        provider="mixed",
        mode="agent",
    )
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(service.generate(QuizGenerateRequest(user_input="测试主题")))

    assert quiz.source_type == "mixed"
    assert len(quiz.sources) == 2
    assert quiz.grounding.provider == "mixed"


def test_research_failure_degrades_to_model_only() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    research = FakeResearchService(error=RuntimeError("boom"))
    service = QuizService(make_settings(), provider, research_service=research)

    quiz = asyncio.run(
        service.generate(QuizGenerateRequest(user_input="Harness Engineering"))
    )

    assert quiz.grounding.status == GroundingStatus.model_only
    assert provider.quiz_calls[0]["topic"] == "Harness Engineering"
    assert provider.quiz_calls[0]["sources"] == []


def test_no_research_service_is_model_only() -> None:
    provider = FakeProvider(quiz_drafts=[draft_with_citations()])
    service = QuizService(make_settings(), provider)

    quiz = asyncio.run(service.generate(QuizGenerateRequest(user_input="RAG")))

    assert quiz.grounding.status == GroundingStatus.model_only
    assert quiz.source_type == "text"
