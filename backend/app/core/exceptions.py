"""统一业务异常与错误码。"""

from __future__ import annotations


class AppError(Exception):
    code: int = 5000
    http_status: int = 500
    default_message: str = "服务器开小差了，请稍后重试"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class InvalidInput(AppError):
    code = 4001
    http_status = 400
    default_message = "请求参数不合法"


class AIProviderError(AppError):
    code = 4002
    http_status = 502
    default_message = "AI 生成失败，请稍后重试"


class ContentRejected(AppError):
    code = 4003
    http_status = 422
    default_message = "内容包含不适宜的主题，请更换学习内容"


class RateLimited(AppError):
    code = 4290
    http_status = 429
    default_message = "请求太频繁了，请稍后再试"


class RouteNotFound(AppError):
    code = 4040
    http_status = 404
    default_message = "接口不存在"


class QuizFormatError(Exception):
    """模型输出不满足题库契约，仅用于服务层内部重试判断。"""


class ReportFormatError(Exception):
    """模型输出不满足报告契约，仅用于服务层内部重试判断。"""
