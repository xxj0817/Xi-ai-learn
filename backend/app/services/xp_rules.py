"""经验值规则（与用户系统需求文档 §5 保持一致）。"""

from __future__ import annotations

XP_PER_COMPLETION = 10
XP_PER_CORRECT = 2


def calculate_xp(correct_count: int) -> int:
    """完成一次闯关 +10 XP，每答对一题额外 +2 XP。"""
    if correct_count < 0:
        raise ValueError("答对题数不能为负数")
    return XP_PER_COMPLETION + correct_count * XP_PER_CORRECT
