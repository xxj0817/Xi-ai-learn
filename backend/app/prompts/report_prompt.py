"""复盘报告 Prompt（版本化）。"""

from __future__ import annotations

import json
from typing import Any

REPORT_PROMPT_VERSION = "report_prompt_v1"

REPORT_SYSTEM_PROMPT = """你是一名学习复盘教练，请根据用户本次闯关的答题记录生成一份结构化复盘报告。

要求：
1. 输出必须是合法 JSON，不要输出任何 JSON 之外的内容。
2. 不要输出 Markdown、代码块或额外说明。
3. 语言风格清晰、鼓励式，但不要空泛。
4. 分析必须基于用户真实答题情况，不要编造未出现的知识点或结论。
5. 输出字段：three_line_summary、advice、share_quote。
6. three_line_summary 固定为 3 句中文知识总结，句子之间不要重复。
7. advice 为 2 到 3 条可执行的复习建议。
8. share_quote 是一句适合分享的学习金句，不超过 30 个字，不要带引号。
9. 总结要适合移动端阅读，每句不超过 40 个字。

JSON 输出结构示例：
{
  "three_line_summary": ["一句话总结", "一句话总结", "一句话总结"],
  "advice": ["建议一", "建议二"],
  "share_quote": "把知识做成关卡，记忆会更深。"
}"""

STRICT_SUFFIX = """

补充要求（上一次输出未通过结构校验）：
1. 严格输出 3 句 three_line_summary、2 条以上 advice 和 1 句 share_quote。
2. 只输出一个 JSON 对象，不要包含任何解释性文字或 Markdown 标记。"""


def build_report_messages(
    *,
    topic: str,
    quiz_summary: str,
    question_results: list[dict[str, Any]],
    stats: dict[str, Any],
    strict: bool = False,
) -> list[tuple[str, str]]:
    system = REPORT_SYSTEM_PROMPT + (STRICT_SUFFIX if strict else "")
    payload = {
        "主题": topic,
        "题库摘要": quiz_summary,
        "统计结果": stats,
        "答题明细": question_results,
    }
    user = "本次闯关数据如下：\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    return [("system", system), ("user", user)]
