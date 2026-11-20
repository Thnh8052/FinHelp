"""The steps of many answers added up (slice 3 of the admin trace, owner 20/11): where questions stop, how long each step takes, what the guard decided and whether the
answer waited for it, the steps dropped for time, and how often "Search deeper" was offered and clicked. `summarize` is pure (a list of stored traces in, numbers out);
`steps_summary` reads the traces of a time window and a user scope from the messages."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Dict, Iterable, List, Optional

from app.infrastructure.database import collections
from app.modules.admin.overview import _day_start, user_scope
from app.modules.admin.steps import explain

LIMIT = 3000  # the newest answers of the window: enough for a median, small enough to read in one request


def _nearest_rank(values: List[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(q * len(ordered)) - 1)]


def summarize(traces: Iterable[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    stopped: Counter = Counter()
    seconds: Dict[str, List[float]] = {}
    labels: Counter = Counter()
    outcomes: Counter = Counter()
    degraded: Counter = Counter()
    waits: List[float] = []
    offered = prominent = clicks = questions = answered = 0
    for t in traces:
        explained = explain(t)
        if not explained["steps"]:
            continue  # an old answer with no trace
        questions += 1
        if explained["stopped_at"]:
            stopped[explained["stopped_at"]] += 1
        else:
            answered += 1
        for step in explained["steps"]:
            if step["seconds"] is not None:
                seconds.setdefault(step["step"], []).append(step["seconds"])
        guard = (t or {}).get("guard") or {}
        if guard.get("label"):
            labels[guard["label"]] += 1
        if guard.get("outcome"):
            outcomes[guard["outcome"]] += 1
        if guard.get("waited_seconds") is not None:
            waits.append(guard["waited_seconds"])
        degraded.update((t or {}).get("degraded") or [])
        more = ((t or {}).get("actions") or {}).get("search_more")
        offered += 1 if more else 0
        prominent += 1 if more and more.get("prominent") else 0
        clicks += 1 if (t or {}).get("click") else 0
    return {
        "questions": questions,
        "answered": answered,
        "stopped": dict(stopped),
        "seconds": {step: {"n": len(v), "p50": round(_nearest_rank(v, 0.5), 2), "p90": round(_nearest_rank(v, 0.9), 2)} for step, v in seconds.items()},
        "guard": {"labels": dict(labels), "outcomes": dict(outcomes), "waited": {"answers": len(waits), "over_half_second": sum(1 for w in waits if w > 0.5)}},
        "degraded": dict(degraded),
        "search_deeper": {"offered": offered, "prominent": prominent, "clicks": clicks},
    }


async def steps_summary(db, days: int = 14, user: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """`summarize` over the newest answers of the last `days` days (of one user, or "guests", or everyone)."""
    now = now or datetime.now(timezone.utc)
    query = {"role": "assistant", "created_at": {"$gte": _day_start(now) - timedelta(days=days - 1)}, **await user_scope(db, user)}
    rows = await db[collections.MESSAGES_COLLECTION].find(query, {"trace_info": 1}).sort("created_at", -1).to_list(LIMIT)
    return {"window_days": days, **summarize(r.get("trace_info") for r in rows)}
