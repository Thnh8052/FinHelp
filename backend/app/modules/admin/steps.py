"""The steps of one answer, read from the trace the chat stored with it (owner 20/11: the admin should see what the system did, and why the guard decided
what it did). A pure function of that trace: no model call, no database; the page turns the codes into words.

Every step is {"step", "outcome", "code", "seconds", "facts"}: `outcome` is ok | warn | stopped | skipped, `code` the decision of the step (the guard's label, the input
rule's action, the rule that chose the documents...), `facts` a few short values and counts, never a long text. A question that was turned away has the steps up to
the one that turned it away (`stopped_at`); the guard of a question an input rule stopped is kept as "skipped", since it ran beside the rules and was not waited for."""
from typing import Any, Dict, List, Optional

from app.infrastructure.database import collections

ORDER = ["gate", "input", "guard", "scope", "plan", "search", "write", "check", "buttons"]
STOP_AT = {"empty_plan": "plan", "out_of_scope": "scope"}  # intents that are not decided by the code gate, the guard or an input rule
CALL_KEYS = ("purpose", "seconds", "attempts", "status", "first_piece_seconds", "thinking", "prompt_tokens", "completion_tokens", "reasoning_tokens",
             "prompt_cache_hit_tokens")
MAX_LISTED = 4
MAX_TEXT = 120


def _num(value: Any) -> Optional[float]:
    return round(float(value), 2) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _text(value: Any) -> str:
    return str(value)[:MAX_TEXT]


def _stopped_at(t: Dict[str, Any]) -> Optional[str]:
    intent = t.get("intent")
    if "gate" in t:
        return "gate"
    if not intent or intent == "retrieval_rag":  # answered: the check may still have replaced the answer
        return "check" if (t.get("review") or {}).get("outcome") == "blocked" else None
    if intent in STOP_AT:
        return STOP_AT[intent]
    if (t.get("guard") or {}).get("outcome") in ("kept", "blocked"):
        return "guard"
    return "input"


def _step(name: str, outcome: str, code: Any = None, seconds: Any = None, **facts: Any) -> Dict[str, Any]:
    return {"step": name, "outcome": outcome, "code": code, "seconds": _num(seconds), "facts": {k: v for k, v in facts.items() if v not in (None, [], {}, "")}}


def _answer_call(t: Dict[str, Any]) -> Dict[str, Any]:
    return next((c for c in (t.get("llm_calls") or []) if c.get("purpose") == "answer"), {})


def explain(trace: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    t = trace or {}
    stop = _stopped_at(t)
    timings, guard, decision, targets = t.get("timings") or {}, t.get("guard") or {}, t.get("decision") or {}, t.get("targets") or {}
    review, verification, meta, llm = t.get("review") or {}, t.get("verification") or {}, t.get("answer_meta") or {}, t.get("llm") or {}
    degraded = t.get("degraded") or []
    steps: Dict[str, Dict[str, Any]] = {}

    gate = t.get("gate") or {}
    if "gate" in t or any(k in t for k in ("guard", "decision", "targets", "plan", "timings", "unlisted_companies")):
        steps["gate"] = _step("gate", "stopped" if stop == "gate" else "ok", gate.get("rule"), signals=gate.get("signals"))

    if decision.get("action"):
        parts = len(t.get("parts") or decision.get("sub_questions") or []) if decision["action"] == "split_questions" else None
        steps["input"] = _step("input", "stopped" if stop == "input" else "ok", decision["action"], assumption=_text(decision["assumption"]) if decision.get("assumption") else None,
                               flags=decision.get("flags"), unlisted=(decision.get("unlisted_companies") or [])[:MAX_LISTED], available=(decision.get("available") or [])[:8], parts=parts)

    if guard:
        raw = guard.get("outcome")
        outcome = "stopped" if stop == "guard" else "skipped" if raw == "not_waited" else "warn" if guard.get("error") or raw == "unchecked" else "ok"
        steps["guard"] = _step("guard", outcome, guard.get("label"), guard.get("seconds"), result=raw, where=guard.get("where"), error=guard.get("error"),
                                waited_seconds=_num(guard.get("waited_seconds")))

    if targets or t.get("unlisted_companies") or stop == "scope":
        steps["scope"] = _step("scope", "stopped" if stop == "scope" else "ok", targets.get("rule"), documents=len(targets.get("documents") or []) or None, routing=t.get("routing"),
                               alternatives=len(t.get("alternatives") or []) or None, unlisted=(t.get("unlisted_companies") or [])[:MAX_LISTED])

    if "plan" in t or "sub_queries" in t or stop == "plan":
        plan = t.get("plan") or []
        steps["plan"] = _step("plan", "stopped" if stop == "plan" else "warn" if "plan_deadline" in degraded else "ok", "empty" if not plan else "planned", timings.get("plan"),
                              items=len(plan), queries=[_text(p.get("query", "")) for p in plan[:MAX_LISTED]])

    if timings.get("search") is not None or t.get("chunk_ids"):
        parts = {f"{k}_seconds": _num(timings.get(f"search_{k}")) for k in ("embed", "vector", "bm25", "mongo_text", "rerank", "hydrate")}
        funnel = t.get("search_counts") or {}
        steps["search"] = _step("search", "warn" if degraded else "ok", None, timings.get("search"), excerpts=len(t.get("chunk_ids") or []), pages=len(t.get("retrieved_pages") or []),
                                degraded=list(degraded), candidates=funnel.get("candidates"), rerank_pairs=funnel.get("rerank_pairs"), tokens=funnel.get("tokens"),
                                max_tokens=funnel.get("max_tokens"), **parts)

    if timings.get("generate") is not None or _answer_call(t):
        call = _answer_call(t)
        steps["write"] = _step("write", "warn" if call.get("status") not in (None, "ok") else "ok", None, timings.get("generate"), first_text_seconds=_num(timings.get("first_text")),
                               prompt_tokens=llm.get("prompt_tokens"), completion_tokens=llm.get("completion_tokens"), reasoning_tokens=llm.get("reasoning_tokens"),
                               notes=len(t.get("notes") or []) or None, status=call.get("status"), attempts=call.get("attempts"))

    if review or verification or meta:
        unverified = verification.get("unverified_figures") or []
        outcome = ("stopped" if review.get("outcome") == "blocked" else "warn" if review.get("outcome") == "annotated" or verification.get("passed") is False
                   or meta.get("status") in ("not_found", "partial") else "ok")
        steps["check"] = _step("check", outcome, review.get("outcome"), timings.get("verify_repair"), findings=len(review.get("first") or []),
                               unverified_figures=len(unverified) or None, status=meta.get("status"))

    actions = t.get("actions") or {}
    if any(actions.values()):
        more = actions.get("search_more")
        steps["buttons"] = _step("buttons", "ok", None, None, search_more=("prominent" if more.get("prominent") else "quiet") if more else None,
                                 chooser=len(actions.get("chooser") or []) or None, edit_question=True if actions.get("edit_question") else None,
                                 try_again=True if actions.get("try_again") else None, why=t.get("actions_why"))

    ordered = [steps[n] for n in ORDER if n in steps]
    if stop:
        cut = ORDER.index(stop)
        ordered = [s for s in ordered if ORDER.index(s["step"]) <= cut or (stop == "input" and s["step"] == "guard")]
    return {
        "steps": ordered,
        "stopped_at": stop if stop in steps else None,
        "total_seconds": _num(timings.get("total")),
        "calls": [{k: (_num(c[k]) if k.endswith("seconds") else c[k]) for k in CALL_KEYS if k in c} for c in (t.get("llm_calls") or [])],
    }


async def answer_steps(db, message_id: str) -> Optional[Dict[str, Any]]:
    """The steps of one stored answer (None when there is no such answer), with the answer's id and total latency."""
    doc = await db[collections.MESSAGES_COLLECTION].find_one({"message_id": message_id, "role": "assistant"}, {"message_id": 1, "latency_ms": 1, "trace_info": 1})
    if not doc:
        return None
    return {"message_id": doc["message_id"], "latency_ms": doc.get("latency_ms"), **explain(doc.get("trace_info"))}
