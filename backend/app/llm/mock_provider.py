"""离线 Mock Provider：无需 API Key 即可跑通完整闭环。"""

from __future__ import annotations

from typing import Any, Sequence

from app.llm.schemas import QuestionDraft, QuestionOptionDraft, QuizDraft, ReportDraft
from app.models.quiz import QuizSource

_TYPE_PLAN = ["single", "single", "single", "multiple", "judge"]


class MockProvider:
    async def generate_quiz(
        self,
        *,
        topic: str,
        question_count: int,
        difficulty: str,
        sources: Sequence[QuizSource] = (),
        strict: bool = False,
    ) -> QuizDraft:
        plan = list(_TYPE_PLAN) if question_count >= len(_TYPE_PLAN) else _TYPE_PLAN[:question_count]
        while len(plan) < question_count:
            plan.append("single")

        source_ids = [source.id for source in sources]
        questions = [
            self._build_question(index, question_type, topic, difficulty, source_ids)
            for index, question_type in enumerate(plan, start=1)
        ]

        return QuizDraft(
            title=f"{topic[:12]} 闯关",
            summary=f"围绕「{topic}」生成的 {question_count} 道闯关题，覆盖概念理解、易错点与应用场景。",
            questions=questions,
        )

    async def generate_report(
        self,
        *,
        topic: str,
        quiz_summary: str,
        question_results: list[dict[str, Any]],
        stats: dict[str, Any],
        strict: bool = False,
    ) -> ReportDraft:
        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        accuracy = stats.get("accuracy", 0)
        mastered = stats.get("mastered_points", []) or []
        weak = stats.get("weak_points", []) or []

        mastered_text = "、".join(mastered) if mastered else "暂未形成明显优势"
        weak_text = "、".join(weak) if weak else "暂无明显薄弱点"

        return ReportDraft(
            three_line_summary=[
                f"本次共 {total} 题，答对 {correct} 题，正确率 {accuracy}%。",
                f"掌握较好：{mastered_text}。",
                f"下一步重点：{weak_text}。",
            ],
            advice=[
                f"把「{topic}」里答错的知识点用自己的话复述一遍。",
                "隔天再刷一次同类题目，巩固长期记忆。",
            ],
            share_quote="把知识做成关卡，记忆会更深。",
        )

    def _build_question(
        self,
        index: int,
        question_type: str,
        topic: str,
        difficulty: str,
        source_ids: Sequence[str] = (),
    ) -> QuestionDraft:
        citations = [source_ids[0]] if source_ids else []
        if question_type == "judge":
            return QuestionDraft(
                type="judge",
                stem=f"判断：学习「{topic}」只需要记住结论，不需要理解过程。",
                options=[
                    QuestionOptionDraft(key="A", text="正确"),
                    QuestionOptionDraft(key="B", text="错误"),
                ],
                answer=["B"],
                explanation=(
                    f"这道判断题考察的是「{topic}」的学习方式。只记结论会在题目换个说法时失效，"
                    "理解概念之间的关系才能真正迁移，所以题干说法错误。"
                ),
                knowledge_point="理解优先于记忆",
                difficulty="easy",
                citations=citations,
            )

        if question_type == "multiple":
            return QuestionDraft(
                type="multiple",
                stem=f"关于「{topic}」，以下哪些说法是成立的？（多选）",
                options=[
                    QuestionOptionDraft(key="A", text="需要先弄清楚核心概念之间的区别"),
                    QuestionOptionDraft(key="B", text="只要背下术语就能灵活应用"),
                    QuestionOptionDraft(key="C", text="结合具体场景练习能加深理解"),
                    QuestionOptionDraft(key="D", text="和已有知识建立联系可以帮助记忆"),
                ],
                answer=["A", "C", "D"],
                explanation=(
                    f"多选题的关键在于区分「理解」和「死记」。围绕「{topic}」，先厘清概念差异，"
                    "再结合场景练习并联系已有知识，才是有效路径；只背术语无法应对变形题。"
                ),
                knowledge_point="学习方法",
                difficulty="medium",
                citations=citations,
            )

        stems = [
            f"关于「{topic}」，下列说法最准确的是？",
            f"学习「{topic}」时，最先应该弄清楚的是什么？",
            f"下面哪种做法最符合「{topic}」的核心思路？",
            f"如果要向同学解释「{topic}」，下面哪个切入角度更合适？",
            f"在「{topic}」的练习中，哪种复盘方式更有效？",
        ]
        explanations = [
            f"这道题考察「{topic}」的核心定义。正确选项对应最基础的概念表述，"
            "另外三个选项都加入了绝对化或超出范围的表述，属于常见干扰项。",
            f"学习「{topic}」应从核心概念入手，先建立整体框架，再补充细节，"
            "否则容易在相似术语之间混淆。",
            f"「{topic}」强调把知识用到具体场景里。只有把概念和实际例子对应起来，"
            "才能在题目换个问法时依然判断正确。",
            f"解释「{topic}」时，从它要解决的问题切入最容易讲清楚，"
            "先说明为什么需要它，再说明它怎么运作。",
            f"复盘「{topic}」时，把错题按知识点归类，比单纯重看答案更有效，"
            "因为这样能定位到真正的薄弱环节。",
        ]
        stem = stems[(index - 1) % len(stems)] if index <= len(stems) else f"第 {index} 题：关于「{topic}」的理解，正确的是？"
        explanation = explanations[(index - 1) % len(explanations)]

        return QuestionDraft(
            type="single",
            stem=stem,
            options=[
                QuestionOptionDraft(key="A", text="先理解概念，再结合场景练习"),
                QuestionOptionDraft(key="B", text="只背结论，不关心推导过程"),
                QuestionOptionDraft(key="C", text="跳过基础，直接做最难的题"),
                QuestionOptionDraft(key="D", text="只看视频，不做任何输出"),
            ],
            answer=["A"],
            explanation=explanation,
            knowledge_point="概念理解",
            difficulty=difficulty if difficulty in {"easy", "medium", "hard"} else "easy",
            citations=citations,
        )
