"""用户输入中的网址识别与清洗。"""

from __future__ import annotations

import re
from typing import Sequence

_URL_RE = re.compile(
    r"https?://[^\s<>\"'\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+",
    re.IGNORECASE,
)
_TRAILING_PUNCT = ".,;:!?)]}>,，。；：！？）】》」』、"


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(_TRAILING_PUNCT)
        if url and url not in urls:
            urls.append(url)
    return urls


def merge_source_urls(
    user_input: str,
    source_urls: Sequence[str],
    *,
    max_urls: int = 3,
) -> list[str]:
    merged: list[str] = []
    for raw in [*extract_urls(user_input), *source_urls]:
        url = str(raw).strip()
        if not url or url in merged:
            continue
        merged.append(url)
        if len(merged) >= max_urls:
            break
    return merged


def strip_urls(text: str) -> str:
    return re.sub(r"\s+", " ", _URL_RE.sub(" ", text or "")).strip()
