"""P7: latency and cost of the answered questions, read from the traces stored with each assistant message (messages.trace_info).

p50 / p95 seconds per stage (plan, search, generate, verify_repair, total), LLM calls and tokens per question, share of answers that
needed the repair call or still carry a flag, share routed by targets / planner + safety net.

  .venv/Scripts/python.exe scripts/latency_report.py [--last 500]
"""
import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.collections import MESSAGES_COLLECTION  # noqa: E402
from app.db.mongodb import MongoManager  # noqa: E402

STAGES = ("plan", "search", "generate", "verify_repair", "total")


def pct(values, q):
    return f"{np.percentile(values, q):.2f}" if values else "-"


async def main(last: int):
    await MongoManager.connect_to_database()
    if MongoManager.db is None:
        print("MongoDB connection failed")
        return
    cursor = MongoManager.db[MESSAGES_COLLECTION].find({"role": "assistant", "trace_info.timings.total": {"$exists": True}},
                                                       {"trace_info": 1, "_id": 0}).sort("created_at", -1).limit(last)
    traces = [m["trace_info"] async for m in cursor]
    print(f"{len(traces)} answered questions (most recent {last})\n")
    if not traces:
        return
    print("| stage | p50 s | p95 s | n |\n|---|---|---|---|")
    for stage in STAGES:
        vals = [t["timings"][stage] for t in traces if isinstance(t.get("timings", {}).get(stage), (int, float))]
        print(f"| {stage} | {pct(vals, 50)} | {pct(vals, 95)} | {len(vals)} |")
    calls = [t.get("llm", {}).get("calls", 0) for t in traces]
    toks = [t.get("llm", {}).get("prompt_tokens", 0) + t.get("llm", {}).get("completion_tokens", 0) for t in traces]
    print(f"\nLLM calls / question: mean {np.mean(calls):.2f}, p95 {pct(calls, 95)}, max {max(calls)}")
    print(f"LLM tokens / question: mean {np.mean(toks):.0f}, p95 {pct(toks, 95)}")
    ver = [t.get("verification") or {} for t in traces]
    print(f"repair call: {sum(v.get('repaired', False) for v in ver) / len(ver):.1%}; still flagged: {sum(v.get('passed') is False for v in ver) / len(ver):.1%}")
    routes = Counter(t.get("routing", t.get("intent", "?")) for t in traces)
    print("routing: " + ", ".join(f"{k} {v}" for k, v in routes.most_common()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=500)
    asyncio.run(main(ap.parse_args().last))
