import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import certifi
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())


def env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return default


def env_list(*names: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(*names, default=default).split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    allowed_origins: list[str]
    allowed_origin_regex: str

    llm_providers: list[str]
    llm_timeout: float
    llm_temperature: float

    openai_api_key: str
    openai_model: str
    openai_fast_model: str

    anthropic_api_key: str
    anthropic_model: str
    anthropic_fast_model: str

    groq_api_key: str
    groq_model: str
    groq_fast_model: str
    groq_backup_models: list[str]

    gemini_api_key: str
    gemini_model: str
    gemini_fast_model: str

    tavily_api_key: str
    openweather_api_key: str
    database_url: str
    tool_timeout: float
    hedge_delay: float
    port: int
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    max_concurrent_runs: int

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_name=env("APP_NAME", default="TripGraph AI"),
        environment=env("ENVIRONMENT", default="development").lower(),
        allowed_origins=env_list(
            "ALLOWED_ORIGINS",
            default="http://localhost:3000,http://127.0.0.1:3000",
        ),
        allowed_origin_regex=env("ALLOWED_ORIGIN_REGEX"),
        llm_providers=[
            name.lower()
            for name in env_list("LLM_PROVIDERS", default="openai,anthropic,groq,gemini")
        ],
        llm_timeout=float(env("LLM_TIMEOUT_SECONDS", default="45")),
        llm_temperature=float(env("LLM_TEMPERATURE", default="0.4")),
        openai_api_key=env("OPENAI_API_KEY"),
        openai_model=env("OPENAI_MODEL", default="gpt-4.1-mini"),
        openai_fast_model=env("OPENAI_FAST_MODEL", default="gpt-4.1-mini"),
        anthropic_api_key=env("ANTHROPIC_API_KEY", "ANTORPIC_API_KEY"),
        anthropic_model=env("ANTHROPIC_MODEL", default="claude-haiku-5-5"),
        anthropic_fast_model=env("ANTHROPIC_FAST_MODEL", default="claude-haiku-5-5"),
        groq_api_key=env("GROQ_API_KEY"),
        groq_model=env("GROQ_MODEL", default="openai/gpt-oss-120b"),
        groq_fast_model=env("GROQ_FAST_MODEL", default="openai/gpt-oss-20b"),
        groq_backup_models=env_list("GROQ_BACKUP_MODELS", default="qwen/qwen3.8-27b"),
        gemini_api_key=env("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        gemini_model=env("GEMINI_MODEL", default="gemini-flash-lite-latest"),
        gemini_fast_model=env("GEMINI_FAST_MODEL", default="gemini-flash-lite-latest"),
        tavily_api_key=env("TAVILY_API_KEY"),
        openweather_api_key=env("OPENWEATHER_API_KEY", "OPENWEATHERMAP_API_KEY"),
        database_url=env("DATABASE_URL"),
        tool_timeout=float(env("TOOL_TIMEOUT_SECONDS", default="12")),
        hedge_delay=float(env("TOOL_HEDGE_SECONDS", default="1.5")),
        port=int(env("PORT", default="8000")),
        rate_limit_per_minute=int(env("RATE_LIMIT_PER_MINUTE", default="8")),
        rate_limit_per_hour=int(env("RATE_LIMIT_PER_HOUR", default="60")),
        max_concurrent_runs=int(env("MAX_CONCURRENT_RUNS", default="6")),
    )
