"""Summaries over stored traces: the llm_calls of many questions (generation/llm_client.REQUEST_CALLS, kept in trace_info.llm_calls), summed up per kind of call.
Used by scripts/latency_report.py; no database here."""
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import numpy as np


def _pct(values: List[float], q: float) -> float:
    return round(float(np.percentile(values, q)), 2)


def calls_by_purpose(traces: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per purpose (guard, plan, answer...), the slowest kind first (by median seconds): n calls, how many did not end ok (failed, cancelled, truncated,
    rejected), seconds p50 / p90 / max, the median seconds to the first piece of the streamed ones (None when none streamed), the mean prompt and completion tokens.
    A trace without llm_calls (stored before 20/11/2026) adds nothing."""
    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        for record in trace.get("llm_calls") or []:
            by[record.get("purpose") or "unspecified"].append(record)
    rows = []
    for purpose, records in by.items():
        seconds = [r["seconds"] for r in records]
        first = [r["first_piece_seconds"] for r in records if r.get("first_piece_seconds") is not None]
        rows.append({"purpose": purpose, "n": len(records), "failed": sum(r.get("status") != "ok" for r in records),
                     "seconds_p50": _pct(seconds, 50), "seconds_p90": _pct(seconds, 90), "seconds_max": max(seconds),
                     "first_piece_p50": _pct(first, 50) if first else None,
                     "prompt_tokens_mean": round(float(np.mean([r.get("prompt_tokens", 0) for r in records]))),
                     "completion_tokens_mean": round(float(np.mean([r.get("completion_tokens", 0) for r in records])))})
    return sorted(rows, key=lambda r: -r["seconds_p50"])
