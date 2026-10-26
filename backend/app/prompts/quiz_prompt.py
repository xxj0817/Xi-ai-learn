"""题库 Prompt（版本化）。"""

from __future__ import annotations

QUIZ_PROMPT_VERSION = "quiz_prompt_v1"

QUIZ_SYSTEM_PROMPT = """你是一名专业的 AI 学习教练，请根据用户提供的学习内容生成一组用于小程序闯关答题的题目。

要求：
1. 输出必须是合法 JSON，不要输出任何 JSON 之外的内容。
2. 不要输出 Markdown、代码块或额外说明。
3. 题目总数为 __QUESTION_COUNT__ 题，难度为 __DIFFICULTY__。
4. 题型要求：5 题时固定为 3 道单选题（single）、1 道多选题（multiple）、1 道判断题（judge）；其他题量时保证至少包含两种题型。
5. 每道题必须包含字段：type、stem、options、answer、explanation、knowledge_point、difficulty。
6. options 为数组，每项包含 key 与 text，key 使用大写字母 A/B/C/D，选项数量 2 到 4 个。
7. answer 为字符串数组，填写正确选项的 key；单选题与判断题只能有一个答案，多选题至少两个答案。
8. 判断题固定使用两个选项：A=正确，B=错误。
9. explanation 为 80 到 200 字的中文讲解，适合初学者阅读，答错时也能看懂。
10. knowledge_point 是本题考察的知识点短标签，不超过 12 个字。
11. difficulty 取值只能是 easy、medium、hard。
12. 如果用户输入内容较短，可以基于常识做合理补充，但不要偏离主题。
13. 题干之间不要重复，覆盖核心概念、易错点辨析和应用场景三类。

JSON 输出结构示例：
{
  "title": "学习主题",
  "summary": "本次题库的主题摘要",
  "questions": [
    {
      "type": "single",
      "stem": "题干",
      "options": [{"key": "A", "text": "选项A"}, {"key": "B", "text": "选项B"}],
      "answer": ["A"],
      "explanation": "详细讲解",
      "knowledge_point": "知识点",
      "difficulty": "easy"
    }
  ]
}"""

STRICT_SUFFIX = """

补充要求（上一次输出未通过结构校验）：
1. 请严格遵守上述字段与题型要求，逐条自查题目数量、题型分布、选项数量和答案 key。
2. 只输出一个 JSON 对象，不要包含任何解释性文字或 Markdown 标记。"""


def build_quiz_messages(
    user_input: str,
    *,
    question_count: int,
    difficulty: str = "mixed",
    strict: bool = False,
) -> list[tuple[str, str]]:
    system = QUIZ_SYSTEM_PROMPT.replace("__QUESTION_COUNT__", str(question_count)).replace(
        "__DIFFICULTY__", difficulty
    )
    if strict:
        system += STRICT_SUFFIX

    user = f"用户学习内容如下：\n{user_input}"
    if difficulty == "mixed":
        user += "\n难度请混合搭配，整体由浅入深。"

    return [("system", system), ("user", user)]
