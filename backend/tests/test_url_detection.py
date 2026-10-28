from __future__ import annotations

from app.services.input_normalizer import extract_urls, merge_source_urls, strip_urls


def test_extract_url_only_input() -> None:
    assert extract_urls("https://example.com/article") == ["https://example.com/article"]
    assert strip_urls("https://example.com/article") == ""


def test_extract_url_with_question() -> None:
    text = "https://example.com/paper 这篇论文讲了什么"

    assert extract_urls(text) == ["https://example.com/paper"]
    assert strip_urls(text) == "这篇论文讲了什么"


def test_extract_multiple_urls_and_trailing_punctuation() -> None:
    text = "看 https://a.com/x，还有 https://b.com/y。以及 https://a.com/x"

    assert extract_urls(text) == ["https://a.com/x", "https://b.com/y"]


def test_merge_source_urls_keeps_order_and_deduplicates() -> None:
    merged = merge_source_urls(
        "参考 https://a.com/1 和 https://b.com/2",
        ["https://b.com/2", "https://c.com/3", "https://d.com/4"],
    )

    assert merged == ["https://a.com/1", "https://b.com/2", "https://c.com/3"]


def test_merge_source_urls_respects_limit() -> None:
    merged = merge_source_urls(
        "https://a.com/1 https://b.com/2 https://c.com/3 https://d.com/4",
        [],
        max_urls=3,
    )

    assert merged == ["https://a.com/1", "https://b.com/2", "https://c.com/3"]


def test_non_http_schemes_are_not_treated_as_urls() -> None:
    text = "ftp://example.com/a javascript:alert(1) 这是什么"

    assert extract_urls(text) == []
    assert strip_urls(text) == "ftp://example.com/a javascript:alert(1) 这是什么"
