from __future__ import annotations

from app.models.quiz import SourceOrigin
from app.search.source_collector import SourceCollector, normalize_url


def make_collector(
    *, search_max: int = 1000, extract_max: int = 2000, total_max: int = 5000
) -> SourceCollector:
    return SourceCollector(
        search_result_max_chars=search_max,
        extract_result_max_chars=extract_max,
        tool_total_max_chars=total_max,
    )


def test_normalize_url_ignores_fragment_and_trailing_slash() -> None:
    assert normalize_url("HTTPS://Example.com/a/#x") == "https://example.com/a"


def test_search_results_dedupe_and_keep_longer_content() -> None:
    collector = make_collector()
    collector.record(
        "tavily_search_quick_global",
        {
            "results": [
                {"title": "短", "url": "https://example.com/a", "content": "短内容"},
                {"title": "长", "url": "https://example.com/a/", "content": "更长的内容"},
            ]
        },
    )

    sources = collector.finalize()

    assert len(sources) == 1
    assert sources[0].snippet == "更长的内容"
    assert sources[0].title == "长"


def test_extract_uses_markdown_heading_as_title() -> None:
    collector = make_collector()
    collector.record(
        "tavily_extract_page",
        {
            "results": [
                {
                    "url": "https://example.com/page",
                    "raw_content": "# Harness Engineering\nBody content",
                }
            ]
        },
    )

    sources = collector.finalize()

    assert len(sources) == 1
    assert sources[0].title == "Harness Engineering"
    assert sources[0].origin == SourceOrigin.web


def test_extract_uses_first_meaningful_line_when_no_heading() -> None:
    collector = make_collector()
    collector.record(
        "tavily_extract_page",
        {
            "results": [
                {
                    "url": "https://example.com/page",
                    "raw_content": "Published Time: 2026-01-01\nHarness Engineering - Wikipedia\nBody content",
                }
            ]
        },
    )

    sources = collector.finalize()

    assert sources[0].title == "Harness Engineering - Wikipedia"



def test_truncates_per_result_and_total_budget() -> None:
    collector = make_collector(search_max=5, extract_max=5, total_max=7)
    collector.record(
        "tavily_search_quick_global",
        {
            "results": [
                {"title": "A", "url": "https://example.com/a", "content": "1234567890"},
                {"title": "B", "url": "https://example.com/b", "content": "abcdefghij"},
            ]
        },
    )

    sources = collector.finalize(web_snippet_max_chars=100, total_max_chars=100)

    assert [source.snippet for source in sources] == ["12345", "ab"]


def test_user_sources_come_first_and_ids_are_sequential() -> None:
    collector = make_collector()
    collector.add_user_text("用户资料正文")
    collector.record(
        "tavily_search_quick_global",
        {"results": [{"title": "W", "url": "https://example.com/w", "content": "网页正文"}]},
    )

    sources = collector.finalize()

    assert [source.id for source in sources] == ["S1", "S2"]
    assert sources[0].origin == SourceOrigin.user
    assert sources[1].origin == SourceOrigin.web


def test_used_urls_filters_web_sources_when_matched() -> None:
    collector = make_collector()
    collector.record(
        "tavily_search_quick_global",
        {
            "results": [
                {"title": "A", "url": "https://example.com/a", "content": "A content"},
                {"title": "B", "url": "https://example.com/b", "content": "B content"},
            ]
        },
    )

    sources = collector.finalize(used_urls=["https://example.com/b"])

    assert len(sources) == 1
    assert sources[0].url == "https://example.com/b"


def test_used_urls_without_match_keeps_all_sources() -> None:
    collector = make_collector()
    collector.record(
        "tavily_search_quick_global",
        {"results": [{"title": "A", "url": "https://example.com/a", "content": "A content"}]},
    )

    sources = collector.finalize(used_urls=["https://example.com/missing"])

    assert len(sources) == 1


def test_error_payload_is_not_recorded() -> None:
    collector = make_collector()

    result = collector.record("tavily_search_quick_global", "ToolException: boom")

    assert result == "ToolException: boom"
    assert collector.finalize() == []
    assert collector.has_web_sources is False


def test_user_page_and_text_truncation() -> None:
    collector = make_collector()
    collector.add_user_page("https://example.com/user", "用户页面正文" + "x" * 20)

    sources = collector.finalize(user_snippet_max_chars=10, total_max_chars=10)

    assert len(sources) == 1
    assert sources[0].snippet == "用户页面正文xxxx"
    assert sources[0].origin == SourceOrigin.user
