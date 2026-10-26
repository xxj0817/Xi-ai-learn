"""跨模块配置。"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["mock", "deepseek"]


class Settings(BaseSettings):
    """应用配置，全部可通过环境变量或 backend/.env 覆盖。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Xi AI Learn API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    llm_provider: LLMProviderName = "mock"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = 30.0
    deepseek_thinking_enabled: bool = False
    # 是否读取系统 HTTP_PROXY/HTTPS_PROXY 环境变量。
    # 默认关闭，避免系统里残留的失效代理导致直连失败。
    deepseek_trust_env_proxy: bool = False
    # 显式指定代理，例如 http://127.0.0.1:7890；留空表示直连。
    deepseek_proxy_url: str = ""
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    llm_top_p: float = Field(default=0.9, gt=0, le=1)

    quiz_temperature: float = Field(default=0.4, ge=0, le=2)
    quiz_max_tokens: int = Field(default=2400, ge=256, le=8192)
    report_temperature: float = Field(default=0.5, ge=0, le=2)
    report_max_tokens: int = Field(default=1400, ge=256, le=8192)

    quiz_default_question_count: int = Field(default=5, ge=3, le=8)
    quiz_min_question_count: int = Field(default=3, ge=1, le=10)
    quiz_max_question_count: int = Field(default=8, ge=1, le=10)
    quiz_min_input_chars: int = Field(default=2, ge=1, le=50)
    quiz_max_input_chars: int = Field(default=2000, ge=50, le=20000)

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=20, ge=1, le=1000)

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:10086",
            "http://127.0.0.1:10086",
        ]
    )

    @model_validator(mode="after")
    def validate_llm_settings(self) -> "Settings":
        if self.quiz_min_question_count > self.quiz_max_question_count:
            raise ValueError("quiz_min_question_count 不能大于 quiz_max_question_count")
        if self.llm_provider == "deepseek" and not self.deepseek_api_key.strip():
            raise ValueError("llm_provider=deepseek 时必须配置 DEEPSEEK_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
