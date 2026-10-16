import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings


class RateLimiter:
    def __init__(self, per_minute: int, per_hour: int):
        self.windows = ((60.0, per_minute), (3600.0, per_hour))
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.last_sweep = time.monotonic()

    def _sweep(self, now: float) -> None:
        if now - self.last_sweep < 300:
            return
        self.last_sweep = now
        for key in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]:
            del self.hits[key]

    def check(self, key: str) -> float | None:
        now = time.monotonic()
        self._sweep(now)
        hits = self.hits[key]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        for window, limit in self.windows:
            if limit <= 0:
                continue
            recent = [t for t in hits if now - t <= window]
            if len(recent) >= limit:
                return max(1.0, window - (now - recent[0]))
        hits.append(now)
        return None

    def reset(self) -> None:
        self.hits.clear()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


_settings = get_settings()
limiter = RateLimiter(_settings.rate_limit_per_minute, _settings.rate_limit_per_hour)


async def rate_limit(request: Request) -> None:
    retry = limiter.check(client_ip(request))
    if retry is not None:
        raise HTTPException(
            status_code=429,
            detail=f"You're sending requests too quickly. Please wait {int(retry)} seconds and try again.",
            headers={"Retry-After": str(int(retry))},
        )
