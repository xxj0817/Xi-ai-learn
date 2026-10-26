"""输入文本清洗与长度校验。"""

from __future__ import annotations

import re

from app.core.exceptions import InvalidInput

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_input(text: str, *, min_chars: int = 2, max_chars: int = 2000) -> str:
    cleaned = _CONTROL_CHARS_RE.sub("", text or "")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    if len(cleaned) < min_chars:
        raise InvalidInput(f"输入内容太短，至少需要 {min_chars} 个字符")
    if len(cleaned) > max_chars:
        raise InvalidInput(f"输入内容不能超过 {max_chars} 个字符")
    return cleaned
