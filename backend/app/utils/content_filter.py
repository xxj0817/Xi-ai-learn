"""敏感词与提示词注入的基础过滤。"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.core.exceptions import ContentRejected

# MVP 阶段使用本地词表，后续可替换为第三方内容安全服务
_SENSITIVE_WORDS: Sequence[str] = (
    "赌博",
    "博彩",
    "代考",
    "毒品",
    "制毒",
    "枪支",
    "炸弹",
    "恐怖袭击",
    "色情",
    "裸聊",
    "自杀",
    "洗钱",
    "办假证",
    "诈骗教程",
)

_INJECTION_PATTERNS: Sequence[re.Pattern[str]] = (
    re.compile(r"忽略(之前|以上|前面)的?(所有)?(指令|提示|设定)"),
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions"),
    re.compile(r"system\s*prompt"),
    re.compile(r"开发者模式"),
    re.compile(r"jailbreak"),
    re.compile(r"越狱模式"),
)


def ensure_safe(text: str) -> None:
    lowered = text.casefold()
    if any(word in lowered for word in _SENSITIVE_WORDS):
        raise ContentRejected()
    if any(pattern.search(lowered) for pattern in _INJECTION_PATTERNS):
        raise ContentRejected()
