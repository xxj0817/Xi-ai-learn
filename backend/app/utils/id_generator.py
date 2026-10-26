"""ID 生成工具。"""

from __future__ import annotations

from uuid import uuid4


def new_quiz_id() -> str:
    return f"quiz_{uuid4().hex[:12]}"
