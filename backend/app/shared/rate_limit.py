"""Sliding-window limits for the endpoints that guess secrets (login, one-time codes). In memory: one limit per server process, reset on restart."""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException


class RateLimiter:
    def __init__(self) -> None:
        self._events: Dict[str, Deque[float]] = defaultdict(deque)

    def _recent(self, key: str, window: float) -> Deque[float]:
        events, now = self._events[key], time.monotonic()
        while events and now - events[0] > window:
            events.popleft()
        if not events:
            self._events.pop(key, None)  # idle keys do not pile up
        return events

    def record(self, key: str) -> None:
        self._events[key].append(time.monotonic())

    def blocked(self, key: str, limit: int, window: float) -> bool:
        return len(self._recent(key, window)) >= limit

    def clear(self, key: str) -> None:
        self._events.pop(key, None)

    def reset(self) -> None:
        self._events.clear()


limiter = RateLimiter()


def enforce(key: str, limit: int, window: float) -> None:
    """429 when `key` has already used its `limit` events in the last `window` seconds."""
    if limiter.blocked(key, limit, window):
        raise HTTPException(status_code=429, detail="Quá nhiều lần thử. Vui lòng đợi ít phút rồi thử lại.", headers={"Retry-After": str(int(window))})
