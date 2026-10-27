"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.exceptions import AppError, RouteNotFound
from app.core.logging import configure_logging
from app.core.security import RateLimiter
from app.llm.base import LearningAIProvider
from app.llm.factory import build_provider
from app.repositories.quiz_repository import QuizRepository
from app.repositories.user_repository import UserRepository
from app.services.wechat_client import HttpWeChatClient, build_wechat_client

logger = logging.getLogger(__name__)


def _envelope(code: int, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "message": message, "data": None})


def create_app(
    *,
    settings: Settings | None = None,
    provider: LearningAIProvider | None = None,
    db: Database | None = None,
    wechat_client: HttpWeChatClient | None = None,
    user_repo: object | None = None,
    quiz_repo: object | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = db if db is not None else (Database(settings) if settings.mysql_enabled else None)
        app.state.db = database
        if database is not None:
            try:
                await database.connect()
            except Exception as exc:  # noqa: BLE001 - 数据库不可用时降级，不让整个服务起不来
                logger.warning("MySQL 连接失败，用户相关能力将不可用：%s", type(exc).__name__)
                app.state.db = None

        if app.state.user_repo is None and app.state.db is not None:
            app.state.user_repo = UserRepository(app.state.db)
        if app.state.quiz_repo is None and app.state.db is not None:
            app.state.quiz_repo = QuizRepository(app.state.db)

        try:
            yield
        finally:
            if app.state.db is not None:
                await app.state.db.close()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.provider = provider or build_provider(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.db = None
    app.state.wechat_client = wechat_client or build_wechat_client(settings)
    app.state.user_repo = user_repo
    app.state.quiz_repo = quiz_repo

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        protected = path.startswith(settings.api_v1_prefix) and not path.endswith("/health")
        if settings.rate_limit_enabled and protected:
            client_ip = request.client.host if request.client else "unknown"
            try:
                app.state.rate_limiter.check(client_ip)
            except AppError as exc:
                return _envelope(exc.code, exc.message, exc.http_status)
        return await call_next(request)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.info("业务异常 code=%s message=%s", exc.code, exc.message)
        return _envelope(exc.code, exc.message, exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            location = ".".join(str(item) for item in first.get("loc", ()) if item not in {"body", "query", "path"})
            detail = f"请求参数不合法：{location} {first.get('msg', '')}".strip()
        else:
            detail = "请求参数不合法"
        return _envelope(4001, detail, 400)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            not_found = RouteNotFound()
            return _envelope(not_found.code, not_found.message, not_found.http_status)
        if exc.status_code == 405:
            return _envelope(4050, "请求方法不支持", 405)
        return _envelope(5000, str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常", exc_info=exc)
        return _envelope(5000, "服务器开小差了，请稍后重试", 500)

    return app


app = create_app()
