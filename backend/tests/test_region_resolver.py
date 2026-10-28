from __future__ import annotations

from app.services.region_resolver import resolve_region


def test_explicit_region_wins() -> None:
    context = resolve_region(region="CN", locale="en-US", accept_language="en-US")

    assert context.country == "china"
    assert context.label == "中国"


def test_explicit_global_region() -> None:
    context = resolve_region(region="global", locale="zh-CN")

    assert context.country is None
    assert context.label == "全球"


def test_chinese_locale_selects_china() -> None:
    context = resolve_region(locale="zh-CN")

    assert context.country == "china"


def test_english_locale_stays_global() -> None:
    context = resolve_region(locale="en-US")

    assert context.country is None


def test_accept_language_fallback() -> None:
    context = resolve_region(accept_language="zh-CN,zh;q=0.9,en;q=0.8")

    assert context.country == "china"


def test_input_language_fallback() -> None:
    context = resolve_region(user_input="我想学习 Harness Engineering")

    assert context.country == "china"


def test_english_input_stays_global() -> None:
    context = resolve_region(user_input="What is Harness Engineering?")

    assert context.country is None


def test_common_region_mapping() -> None:
    assert resolve_region(region="JP").country == "japan"
    assert resolve_region(region="US").country == "united states"
    assert resolve_region(region="KR").country == "south korea"


def test_unknown_region_is_global() -> None:
    context = resolve_region(region="XX")

    assert context.country is None
    assert context.label == "全球"
