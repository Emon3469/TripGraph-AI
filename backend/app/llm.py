import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.config import Settings, get_settings

logger = logging.getLogger("tripgraph.llm")

Tier = Literal["fast", "smart"]

AUTH_COOLDOWN_SECONDS = 600
RATE_LIMIT_COOLDOWN_SECONDS = 60
TRANSIENT_COOLDOWN_SECONDS = 20
SHORT_WAIT_SECONDS = 6.0
RETRY_ROUNDS = 2
RETRY_ROUND_WAIT_SECONDS = 15.0


class AllProvidersFailed(RuntimeError):
    pass


@dataclass
class Endpoint:
    provider: str
    model_name: str
    model: BaseChatModel
    disabled_until: float = 0.0
    last_error: str = ""

    @property
    def available(self) -> bool:
        return time.monotonic() >= self.disabled_until


def _openai(s: Settings) -> Callable[[str], BaseChatModel] | None:
    if not s.openai_api_key:
        return None
    from langchain_openai import ChatOpenAI

    return lambda model: ChatOpenAI(
        model=model,
        api_key=s.openai_api_key,
        temperature=s.llm_temperature,
        timeout=s.llm_timeout,
        max_retries=0,
    )


def _anthropic(s: Settings) -> Callable[[str], BaseChatModel] | None:
    if not s.anthropic_api_key:
        return None
    from langchain_anthropic import ChatAnthropic

    return lambda model: ChatAnthropic(
        model=model,
        api_key=s.anthropic_api_key,
        temperature=s.llm_temperature,
        max_tokens=4096,
        default_request_timeout=s.llm_timeout,
        max_retries=0,
    )


def _groq(s: Settings) -> Callable[[str], BaseChatModel] | None:
    if not s.groq_api_key:
        return None
    from langchain_groq import ChatGroq

    def build(model: str) -> BaseChatModel:
        options = {}
        if "gpt-oss" in model:
            options["reasoning_effort"] = "low"
        elif "qwen3" in model:
            options["reasoning_effort"] = "none"
        return ChatGroq(
            model=model,
            api_key=s.groq_api_key,
            temperature=s.llm_temperature,
            timeout=s.llm_timeout,
            max_retries=0,
            **options,
        )

    return build


def _gemini(s: Settings) -> Callable[[str], BaseChatModel] | None:
    if not s.gemini_api_key:
        return None
    from langchain_google_genai import ChatGoogleGenerativeAI

    return lambda model: ChatGoogleGenerativeAI(
        model=model,
        google_api_key=s.gemini_api_key,
        temperature=s.llm_temperature,
        timeout=s.llm_timeout,
        max_retries=0,
    )


FACTORIES = {
    "openai": (_openai, "openai_model", "openai_fast_model"),
    "anthropic": (_anthropic, "anthropic_model", "anthropic_fast_model"),
    "groq": (_groq, "groq_model", "groq_fast_model"),
    "gemini": (_gemini, "gemini_model", "gemini_fast_model"),
}


def chunk_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


def _status_code(error: Exception) -> int | None:
    for attr in ("status_code", "code", "status"):
        value = getattr(error, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(error, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


def _retry_after(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    try:
        value = headers.get("retry-after")
        if value:
            return float(value)
    except (TypeError, ValueError, AttributeError):
        pass
    match = re.search(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", str(error))
    if not match:
        return None
    minutes = float(match.group(1) or 0)
    amount = float(match.group(2))
    return minutes * 60 + (amount / 1000 if match.group(3) == "ms" else amount)


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _classify(error: Exception) -> str:
    status = _status_code(error)
    text = str(error).lower()
    if status == 429 or "rate limit" in text or "resource_exhausted" in text:
        return "rate_limit"
    if status in (401, 402, 403) or any(
        marker in text
        for marker in ("invalid api key", "incorrect api key", "api_key_invalid", "unauthorized", "credit balance")
    ):
        return "auth"
    if status == 404 or "no longer available" in text or "model_not_found" in text:
        return "model"
    return "transient"


class LLMRouter:
    def __init__(self, settings: Settings):
        self.endpoints: dict[tuple[str, str], Endpoint] = {}
        self.order: dict[str, list[Endpoint]] = {"smart": [], "fast": []}
        for name in settings.llm_providers:
            spec = FACTORIES.get(name)
            if not spec:
                logger.warning("Unknown LLM provider '%s' ignored", name)
                continue
            factory, smart_attr, fast_attr = spec
            build = factory(settings)
            if build is None:
                continue
            smart = self._endpoint(name, getattr(settings, smart_attr), build)
            fast = self._endpoint(name, getattr(settings, fast_attr), build)
            backups = [
                self._endpoint(name, model, build)
                for model in (settings.groq_backup_models if name == "groq" else [])
            ]
            for tier, primary in (("smart", [smart, fast]), ("fast", [fast, smart])):
                for endpoint in [*primary, *backups]:
                    if endpoint not in self.order[tier]:
                        self.order[tier].append(endpoint)
        if not self.endpoints:
            logger.error("No LLM provider is configured. Add at least one API key.")

    def _endpoint(self, provider: str, model_name: str, build: Callable[[str], BaseChatModel]) -> Endpoint:
        key = (provider, model_name)
        if key not in self.endpoints:
            self.endpoints[key] = Endpoint(provider=provider, model_name=model_name, model=build(model_name))
        return self.endpoints[key]

    def _candidates(self, tier: Tier) -> list[Endpoint]:
        now = time.monotonic()
        ordered = self.order[tier]
        usable = [e for e in ordered if e.disabled_until - now <= SHORT_WAIT_SECONDS]
        return usable or list(ordered)

    @staticmethod
    async def _await_cooldown(endpoint: Endpoint, budget: list[float]) -> None:
        remaining = endpoint.disabled_until - time.monotonic()
        if 0 < remaining <= budget[0]:
            budget[0] -= remaining
            await asyncio.sleep(remaining)

    def _mark_failed(self, endpoint: Endpoint, error: Exception) -> str:
        kind = _classify(error)
        message = f"{type(error).__name__}: {str(error)[:200]}"
        if kind == "auth":
            targets = [e for e in self.endpoints.values() if e.provider == endpoint.provider]
            cooldown = AUTH_COOLDOWN_SECONDS
        else:
            targets = [endpoint]
            if kind == "rate_limit":
                retry = _retry_after(error)
                cooldown = min(max(retry, 2.0), 3600.0) if retry is not None else RATE_LIMIT_COOLDOWN_SECONDS
            elif kind == "model":
                cooldown = AUTH_COOLDOWN_SECONDS
            else:
                cooldown = TRANSIENT_COOLDOWN_SECONDS
        until = time.monotonic() + cooldown
        for target in targets:
            target.disabled_until = until
            target.last_error = message
        logger.warning(
            "LLM %s/%s failed (%s), cooling down %.0fs: %s",
            endpoint.provider, endpoint.model_name, kind, cooldown, message,
        )
        return kind

    @staticmethod
    def _mark_ok(endpoint: Endpoint) -> None:
        endpoint.disabled_until = 0.0
        endpoint.last_error = ""

    def _retry_delay(self, tier: Tier) -> float | None:
        now = time.monotonic()
        waits = [e.disabled_until - now for e in self.order[tier]]
        soon = [w for w in waits if 0 < w <= RETRY_ROUND_WAIT_SECONDS]
        if any(w <= 0 for w in waits):
            return 0.0
        return min(soon) if soon else None

    async def ainvoke(self, messages: list[BaseMessage], tier: Tier = "smart") -> tuple[str, str]:
        errors: list[str] = []
        blocked: set[str] = set()
        for attempt in range(RETRY_ROUNDS):
            budget = [SHORT_WAIT_SECONDS]
            for endpoint in self._candidates(tier):
                if endpoint.provider in blocked:
                    continue
                await self._await_cooldown(endpoint, budget)
                try:
                    response = await endpoint.model.ainvoke(messages)
                    text = _clean(chunk_text(response.content))
                    if not text:
                        raise ValueError("empty response")
                    self._mark_ok(endpoint)
                    return text, endpoint.provider
                except Exception as error:
                    if self._mark_failed(endpoint, error) == "auth":
                        blocked.add(endpoint.provider)
                    errors.append(f"{endpoint.provider}/{endpoint.model_name}: {error}")
            delay = self._retry_delay(tier)
            if delay is None or attempt == RETRY_ROUNDS - 1:
                break
            logger.info("All LLM providers busy, retrying in %.1fs", delay)
            await asyncio.sleep(delay)
        raise AllProvidersFailed("; ".join(errors) or "No LLM provider configured")

    async def astream(
        self, messages: list[BaseMessage], tier: Tier = "smart"
    ) -> AsyncIterator[tuple[str, str]]:
        errors: list[str] = []
        blocked: set[str] = set()
        for attempt in range(RETRY_ROUNDS):
            budget = [SHORT_WAIT_SECONDS]
            for endpoint in self._candidates(tier):
                if endpoint.provider in blocked:
                    continue
                await self._await_cooldown(endpoint, budget)
                emitted = False
                try:
                    async for chunk in endpoint.model.astream(messages):
                        text = chunk_text(chunk.content)
                        if text:
                            if not emitted:
                                yield "provider", endpoint.provider
                            emitted = True
                            yield "token", text
                    if not emitted:
                        raise ValueError("empty response")
                    self._mark_ok(endpoint)
                    return
                except Exception as error:
                    if self._mark_failed(endpoint, error) == "auth":
                        blocked.add(endpoint.provider)
                    errors.append(f"{endpoint.provider}/{endpoint.model_name}: {error}")
                    if emitted:
                        yield "reset", endpoint.provider
            delay = self._retry_delay(tier)
            if delay is None or attempt == RETRY_ROUNDS - 1:
                break
            logger.info("All LLM providers busy, retrying in %.1fs", delay)
            yield "waiting", f"{delay:.0f}"
            await asyncio.sleep(delay)
        raise AllProvidersFailed("; ".join(errors) or "No LLM provider configured")

    def status(self) -> list[dict]:
        return [
            {
                "provider": e.provider,
                "model": e.model_name,
                "available": e.available,
                "last_error": e.last_error or None,
            }
            for e in self.endpoints.values()
        ]


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter(get_settings())
    return _router
