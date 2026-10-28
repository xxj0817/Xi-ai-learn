"""Tavily 工具结果采集、截断与来源编号。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Sequence
from urllib.parse import urlsplit, urlunsplit

from app.models.quiz import QuizSource, SourceOrigin

logger = logging.getLogger(__name__)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_MARKDOWN_HEADING_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)


def _clean(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _CONTROL_CHARS_RE.sub("", text or "")).strip()


def normalize_url(url: str) -> str:
    """用于去重与 used_urls 匹配的规范化 URL。"""
    parts = urlsplit((url or "").strip())
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, parts.query, ""))


def _derive_title(content: str, url: str) -> str:
    match = _MARKDOWN_HEADING_RE.search(content or "")
    if match:
        return _clean(match.group(1))[:120]
    for raw_line in (content or "").splitlines():
        line = _clean(raw_line.lstrip("# ").strip())
        if not line or line.lower().startswith("published time:"):
            continue
        if len(line) < 3:
            continue
        if len(line) <= 160:
            return line[:120]
        break
    host = urlsplit(url or "").netloc
    return host or "网页来源"


@dataclass
class _Candidate:
    url: str
    title: str
    content: str
    origin: SourceOrigin
    published_date: str | None
    score: float
    order: int


class SourceCollector:
    """收集一次研究过程中的所有工具结果，并产出带编号的来源。"""

    def __init__(
        self,
        *,
        search_result_max_chars: int,
        extract_result_max_chars: int,
        tool_total_max_chars: int,
    ) -> None:
        self._search_result_max_chars = search_result_max_chars
        self._extract_result_max_chars = extract_result_max_chars
        self._tool_total_max_chars = tool_total_max_chars
        self._candidates: dict[str, _Candidate] = {}
        self._next_order = 0

    def add_user_text(self, text: str, *, title: str = "用户提供的资料") -> None:
        cleaned = _clean(text)
        if not cleaned:
            return
        self._store(
            f"user:{self._next_order}",
            _Candidate(
                url="",
                title=title,
                content=cleaned,
                origin=SourceOrigin.user,
                published_date=None,
                score=0.0,
                order=self._next_order,
            ),
        )

    def add_user_page(self, url: str, content: str, *, title: str = "") -> None:
        cleaned = _clean(content)
        if not cleaned or not url:
            return
        self._store(
            normalize_url(url),
            _Candidate(
                url=url.strip(),
                title=_clean(title) or _derive_title(content, url),
                content=cleaned,
                origin=SourceOrigin.user,
                published_date=None,
                score=0.0,
                order=self._next_order,
            ),
        )

    def mark_user_urls(self, urls: Sequence[str]) -> None:
        """把用户显式提供的网址标记为用户来源，保证它们排在网页来源之前。"""
        for url in urls:
            candidate = self._candidates.get(normalize_url(url))
            if candidate is not None:
                candidate.origin = SourceOrigin.user

    def record(self, tool_name: str, result: Any) -> Any:
        """记录工具结果并返回给 Agent 的精简版本。"""
        data = result
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except (TypeError, ValueError):
                return result
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return result

        is_extract = "extract" in tool_name
        per_result_cap = (
            self._extract_result_max_chars if is_extract else self._search_result_max_chars
        )
        remaining_total = self._tool_total_max_chars
        compact_results: list[dict[str, Any]] = []

        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            raw_content = str(item.get("raw_content") or item.get("content") or "")
            content = _clean(raw_content)
            if not content:
                continue
            if len(content) > per_result_cap:
                content = content[:per_result_cap]
            if remaining_total <= 0:
                break
            if len(content) > remaining_total:
                content = content[:remaining_total]
            remaining_total -= len(content)

            title = _clean(str(item.get("title") or "")) or _derive_title(raw_content, url)
            published_date = item.get("published_date")
            if published_date is not None:
                published_date = str(published_date)
            try:
                score = float(item.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0

            self._store(
                normalize_url(url),
                _Candidate(
                    url=url,
                    title=title,
                    content=content,
                    origin=SourceOrigin.web,
                    published_date=published_date,
                    score=score,
                    order=self._next_order,
                ),
            )
            compact_results.append(
                {
                    "title": title,
                    "url": url,
                    "content": content,
                    "score": score,
                    **({"published_date": published_date} if published_date else {}),
                }
            )

        return {"results": compact_results}

    def finalize(
        self,
        *,
        used_urls: Sequence[str] = (),
        max_sources: int = 6,
        web_snippet_max_chars: int = 1200,
        user_snippet_max_chars: int = 4000,
        total_max_chars: int = 12000,
    ) -> list[QuizSource]:
        candidates = list(self._candidates.values())
        user_sources = sorted(
            (item for item in candidates if item.origin == SourceOrigin.user),
            key=lambda item: item.order,
        )
        web_sources = [item for item in candidates if item.origin == SourceOrigin.web]

        if used_urls:
            used = {normalize_url(url) for url in used_urls if url}
            matched = [item for item in web_sources if normalize_url(item.url) in used]
            if matched:
                web_sources = matched

        web_sources.sort(key=lambda item: (-item.score, item.order))
        selected = (user_sources + web_sources)[:max_sources]

        sources: list[QuizSource] = []
        total = 0
        for item in selected:
            snippet_cap = (
                user_snippet_max_chars
                if item.origin == SourceOrigin.user
                else web_snippet_max_chars
            )
            snippet = item.content[:snippet_cap]
            remaining = total_max_chars - total
            if remaining <= 0:
                break
            if len(snippet) > remaining:
                snippet = snippet[:remaining]
            total += len(snippet)
            sources.append(
                QuizSource(
                    id=f"S{len(sources) + 1}",
                    title=item.title or item.url or "来源",
                    url=item.url,
                    snippet=snippet,
                    published_date=item.published_date,
                    origin=item.origin,
                )
            )
        return sources

    @property
    def has_web_sources(self) -> bool:
        return any(item.origin == SourceOrigin.web for item in self._candidates.values())

    def _store(self, key: str, candidate: _Candidate) -> None:
        candidate.order = self._next_order
        self._next_order += 1
        existing = self._candidates.get(key)
        if existing is None:
            self._candidates[key] = candidate
            return
        if len(candidate.content) > len(existing.content):
            candidate.order = existing.order
            self._candidates[key] = candidate
        elif not existing.title and candidate.title:
            existing.title = candidate.title
