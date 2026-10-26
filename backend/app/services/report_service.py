"""复盘报告服务：服务端判分 + LLM 生成 + 结果兜底。"""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import AIProviderError, AppError
from app.llm.base import LearningAIProvider
from app.models.report import Report, ReportGenerateRequest
from app.services.scoring_service import ScoreSummary, build_score_summary

logger = logging.getLogger(__name__)

_FALLBACK_ADVICE = [
    "把本次答错的知识点用自己的话复述一遍，再对照解析找差距。",
    "隔天再刷一次同类题目，检验记忆是否真正留存。",
]
_FALLBACK_QUOTE = "把知识做成关卡，记忆会更深。"
_FALLBACK_MASTERED = "继续保持练习节奏"
_FALLBACK_WEAK = "尝试更高难度的题目"


class ReportService:
    def __init__(self, provider: LearningAIProvider) -> None:
        self._provider = provider

    async def generate(self, request: ReportGenerateRequest) -> Report:
        summary = build_score_summary(request.questions, request.answer_records)
        stats = self._build_stats(summary)
        question_results = [result.model_dump() for result in summary.results]

        try:
            draft = await self._provider.generate_report(
                topic=request.topic,
                quiz_summary=f"{request.topic} · 共 {summary.total} 题",
                question_results=question_results,
                stats=stats,
            )
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一收敛为生成失败
            logger.warning("报告生成失败 error=%s", type(exc).__name__)
            raise AIProviderError() from exc

        if draft is None:
            raise AIProviderError()

        return Report(
            accuracy=summary.accuracy,
            total=summary.total,
            correct=summary.correct,
            mastered_points=summary.mastered_points,
            weak_points=summary.weak_points,
            three_line_summary=self._normalize_summary(draft.three_line_summary, summary),
            advice=self._normalize_advice(draft.advice),
            share_quote=self._normalize_quote(draft.share_quote),
        )

    def _build_stats(self, summary: ScoreSummary) -> dict[str, Any]:
        return {
            "total": summary.total,
            "correct": summary.correct,
            "accuracy": summary.accuracy,
            "mastered_points": summary.mastered_points,
            "weak_points": summary.weak_points,
        }

    def _normalize_summary(self, lines: list[str], summary: ScoreSummary) -> list[str]:
        cleaned = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
        defaults = [
            f"本次共 {summary.total} 题，答对 {summary.correct} 题，正确率 {summary.accuracy}%。",
            f"掌握较好：{'、'.join(summary.mastered_points) or _FALLBACK_MASTERED}。",
            f"下一步重点：{'、'.join(summary.weak_points) or _FALLBACK_WEAK}。",
        ]

        result: list[str] = []
        for line in cleaned:
            if len(result) < 3 and line not in result:
                result.append(line)
        while len(result) < 3:
            candidate = defaults[len(result)]
            if candidate in result:
                candidate = f"复盘提示：{candidate}"
            result.append(candidate)
        return result[:3]

    def _normalize_advice(self, advice: list[str]) -> list[str]:
        cleaned = [item.strip() for item in advice if isinstance(item, str) and item.strip()]
        return cleaned[:3] if cleaned else list(_FALLBACK_ADVICE)

    def _normalize_quote(self, quote: str) -> str:
        cleaned = (quote or "").strip()
        return cleaned or _FALLBACK_QUOTE
