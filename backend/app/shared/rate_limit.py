"""Sliding-window limits for the endpoints that guess secrets (login, one-time codes) and for what guests may spend.
In memory: one limit per server process, reset on restart. ponytail: several uvicorn workers would each count on their own; move this to a shared store then."""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

DAY_SECONDS = 24 * 60 * 60


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

    def forget_latest(self, key: str) -> None:
        """Take back the last event of `key`: it turned out not to count."""
        events = self._events.get(key)
        if events:
            events.pop()

    def clear(self, key: str) -> None:
        self._events.pop(key, None)

    def reset(self) -> None:
        self._events.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(key: str, limit: int, window: float, detail: str = "Quá nhiều lần thử. Vui lòng đợi ít phút rồi thử lại.") -> None:
    """429 when `key` has already used its `limit` events in the last `window` seconds."""
    if limiter.blocked(key, limit, window):
        raise HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(int(window))})


def spend_guest_allowance(request: Request, action: str, limit: int) -> None:
    """One use of what a guest may do per day, counted per address (a guest has no account to count on); 429 past `limit`.
    No await between the check and the count, so requests sent together cannot pass it."""
    key = f"guest:{action}:{client_ip(request)}"
    enforce(key, limit, DAY_SECONDS, "Bạn đã dùng hết lượt dùng thử của hôm nay. Vui lòng đăng nhập để tiếp tục.")
    limiter.record(key)
