"""Read-only numbers for the admin dashboard (GET /auth/admin/overview): questions and tokens per day, the processing state of every
recent PDF, the answers users marked wrong, recent answers for audit and the user list. One request feeds every page of the dashboard."""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.infrastructure.database import collections
from app.modules.chat.trace_stats import _pct

DOCUMENT_LIMIT = 100
MESSAGE_LIMIT = 100
FLAGGED_LIMIT = 50
USER_LIMIT = 200
ANSWER_PREVIEW_CHARS = 3000


def _day_start(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


async def user_scope(db: AsyncIOMotorDatabase, user: Optional[str]) -> Dict[str, Any]:
    """The messages / documents filter of one user's chats ("guests": every guest chat); {} for everyone (owner 19/11: filter the dashboard by user)."""
    if not user:
        return {}
    owner = {"owner_type": "guest"} if user == "guests" else {"owner_type": "user", "owner_id": user}
    notebooks = await db[collections.NOTEBOOKS_COLLECTION].find(owner, {"notebook_id": 1}).to_list(None)
    return {"notebook_id": {"$in": [n["notebook_id"] for n in notebooks]}}


async def _window_totals(messages, start: datetime, end: datetime, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": start, "$lt": end}, **(scope or {})}},
        {"$group": {
            "_id": None,
            "questions": {"$sum": 1},
            "tokens": {"$sum": {"$ifNull": ["$token_usage.total_tokens", 0]}},
            "latency_ms": {"$avg": "$latency_ms"},
        }},
    ]).to_list(1)
    row = rows[0] if rows else {}
    return {"questions": row.get("questions", 0), "tokens": row.get("tokens", 0), "avg_latency_ms": row.get("latency_ms")}


async def _owner_labels(db: AsyncIOMotorDatabase, notebook_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """notebook_id -> {owner_type, username}: who asked or uploaded (guests have no account)."""
    notebooks = await db[collections.NOTEBOOKS_COLLECTION].find(
        {"notebook_id": {"$in": list(set(notebook_ids))}}, {"notebook_id": 1, "owner_type": 1, "owner_id": 1, "title": 1}
    ).to_list(None)
    user_ids = [n["owner_id"] for n in notebooks if n.get("owner_type") == "user"]
    users = await db[collections.USERS_COLLECTION].find({"user_id": {"$in": user_ids}}, {"user_id": 1, "username": 1}).to_list(None)
    names = {u["user_id"]: u["username"] for u in users}
    return {
        n["notebook_id"]: {"owner_type": n.get("owner_type", "user"), "username": names.get(n.get("owner_id")), "notebook_title": n.get("title")}
        for n in notebooks
    }


def model_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Questions and tokens per model of the window; model None = answers that called no model (fixed replies, refusals), not an unknown model."""
    return [{"model": row["_id"], "questions": row["questions"], "tokens": row["tokens"]} for row in rows]


def purpose_rows(traces: List[Dict[str, Any]], prices: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """The model calls of the window per purpose (guard, plan, answer...: llm_client.chat_completion's `purpose`), most tokens first: calls, calls that did
    not end ok, seconds p50 / p90, prompt / completion tokens and the share of all tokens. Traces without llm_calls (before 20/11/2026) add nothing."""
    by: Dict[str, List[Dict[str, Any]]] = {}
    for trace in traces:
        for record in trace.get("llm_calls") or []:
            by.setdefault(record.get("purpose") or "unspecified", []).append(record)
    rows = []
    for purpose, records in by.items():
        seconds = [r.get("seconds") or 0.0 for r in records]
        prompt = sum(r.get("prompt_tokens") or 0 for r in records)
        completion = sum(r.get("completion_tokens") or 0 for r in records)
        rows.append({"purpose": purpose, "calls": len(records), "failed": sum(r.get("status") != "ok" for r in records),
                     "seconds_p50": _pct(seconds, 50), "seconds_p90": _pct(seconds, 90),
                     "prompt_tokens": prompt, "completion_tokens": completion, "tokens": prompt + completion,
                     **({"cost_usd": round(sum(call_cost(r, prices) for r in records), 6)} if prices else {})})
    total = sum(r["tokens"] for r in rows)
    for r in rows:
        r["share"] = round(r["tokens"] / total, 3) if total else 0.0
    return sorted(rows, key=lambda r: -r["tokens"])


def call_cost(record: Dict[str, Any], prices: Dict[str, float]) -> float:
    """Dollars of one model call: cache hits, cache misses and output tokens at their own prices (dollars per million tokens; reasoning tokens are part
    of the output). A record without the cache split counts its whole prompt as misses."""
    hit, miss = record.get("prompt_cache_hit_tokens") or 0, record.get("prompt_cache_miss_tokens") or 0
    if hit + miss == 0:
        miss = record.get("prompt_tokens") or 0
    return round((hit * prices["hit"] + miss * prices["miss"] + (record.get("completion_tokens") or 0) * prices["out"]) / 1e6, 6)


def answer_cost(message: Dict[str, Any], prices: Dict[str, float]) -> tuple:
    """(dollars, estimated) of one stored answer: the sum of its model calls, or for an answer stored before 20/11/2026 (no llm_calls) its token_usage with
    the whole prompt at the cache-miss price (estimated: True)."""
    calls = ((message.get("trace_info") or {}).get("llm_calls")) or []
    if calls:
        return round(sum(call_cost(c, prices) for c in calls), 6), False
    usage = message.get("token_usage") or {}
    if not (usage.get("prompt_tokens") or usage.get("completion_tokens")):
        return 0.0, False
    return call_cost(usage, prices), True


def cost_rows(answers: List[Dict[str, Any]], owners: Dict[str, Dict[str, Any]], prices: Dict[str, float]) -> Dict[str, Any]:
    """Dollars of the window: in all, per day (UTC), per model (None = no model call) and per user (None = guests), and the share of the answers with a
    cost that were estimated from their tokens."""
    total, per_day, by_model, by_user = 0.0, {}, {}, {}
    paid = estimated = 0
    for a in answers:
        usd, guess = answer_cost(a, prices)
        total += usd
        paid += usd > 0
        estimated += guess
        day = a["created_at"].strftime("%Y-%m-%d")
        per_day[day] = per_day.get(day, 0.0) + usd
        by_model[a.get("model_used")] = by_model.get(a.get("model_used"), 0.0) + usd
        owner = owners.get(a.get("notebook_id")) or {}
        user = owner.get("username") if owner.get("owner_type") == "user" else None
        by_user[user] = by_user.get(user, 0.0) + usd
    rnd = lambda d: {k: round(v, 6) for k, v in d.items()}  # noqa: E731
    return {"total_usd": round(total, 6), "estimated_share": round(estimated / paid, 3) if paid else 0.0,
            "per_day": rnd(per_day), "by_model": rnd(by_model), "by_user": rnd(by_user)}


def job_times(timings: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """Waiting (for the worker, then for one of the GPU parse slots) apart from the work of one upload. `total` counts both: a 2-page file that waited
    1,820 s behind 12 others showed "1,862 s" (O1, 26/11). None for a job not finished."""
    if timings.get("total") is None:
        return {"wait_s": None, "work_s": None}
    wait = round((timings.get("queue_wait") or 0.0) + (timings.get("docling_slot_wait_s") or 0.0), 2)
    return {"wait_s": wait, "work_s": round(max(timings["total"] - wait, 0.0), 2)}


def upload_time_summary(times: List[Dict[str, Optional[float]]]) -> Dict[str, Any]:
    """Median and p90 of the wait and of the work over the finished uploads listed (job_times)."""
    done = [t for t in times if t["wait_s"] is not None]
    if not done:
        return {"files": 0, "wait_p50": None, "wait_p90": None, "work_p50": None, "work_p90": None}
    waits, works = [t["wait_s"] for t in done], [t["work_s"] for t in done]
    return {"files": len(done), "wait_p50": _pct(waits, 50), "wait_p90": _pct(waits, 90), "work_p50": _pct(works, 50), "work_p90": _pct(works, 90)}


def top_users(rows: List[Dict[str, Any]], owners: Dict[str, Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
    """The users who used the most tokens in the window, from the tokens per notebook (`rows`) and who owns each notebook (_owner_labels). Guests have
    no account: they are one row with username None. A notebook no longer stored is left out."""
    tokens: Dict[Optional[str], int] = {}
    for row in rows:
        owner = owners.get(row["_id"])
        if owner is None or not row["tokens"]:
            continue
        name = owner.get("username") if owner.get("owner_type") == "user" else None
        tokens[name] = tokens.get(name, 0) + row["tokens"]
    return [{"username": name, "tokens": n} for name, n in sorted(tokens.items(), key=lambda kv: -kv[1])[:limit]]


async def _answers(db: AsyncIOMotorDatabase, query: Dict[str, Any], limit: int, newest_by: str = "created_at",
                   extra: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Assistant answers matching `query`, newest first by `newest_by`, each with the question asked just before it and who asked. `extra` adds fields
    read from the stored answer (the review queue: its problem labels and review)."""
    messages = db[collections.MESSAGES_COLLECTION]
    answers = await messages.find({"role": "assistant", **query}).sort(newest_by, -1).limit(limit).to_list(limit)
    if not answers:
        return []
    question_keys = [{"notebook_id": a["notebook_id"], "message_index": a.get("message_index", 0) - 1} for a in answers]
    questions = await messages.find({"role": "user", "$or": question_keys}, {"notebook_id": 1, "message_index": 1, "content": 1}).to_list(None)
    asked = {(q["notebook_id"], q["message_index"]): q["content"] for q in questions}
    owners = await _owner_labels(db, [a["notebook_id"] for a in answers])
    return [
        {
            "message_id": a["message_id"],
            "notebook_id": a["notebook_id"],
            "question": asked.get((a["notebook_id"], a.get("message_index", 0) - 1), ""),
            "answer": (a.get("content") or "")[:ANSWER_PREVIEW_CHARS],
            "tokens": (a.get("token_usage") or {}).get("total_tokens", 0),
            "latency_ms": a.get("latency_ms"),
            "model": a.get("model_used"),
            "rating": a.get("user_rating"),
            "rated_at": a.get("rated_at"),
            "citations": len(a.get("citations") or []),
            "created_at": a.get("created_at"),
            **owners.get(a["notebook_id"], {"owner_type": "unknown", "username": None, "notebook_title": None}),
            **(extra(a) if extra else {}),
        }
        for a in answers
    ]


async def build_overview(db: AsyncIOMotorDatabase, days: int, user: Optional[str] = None) -> Dict[str, Any]:
    """`user` narrows questions, tokens, documents and answers to one user's chats ("guests": the guest chats); the user list stays whole."""
    now = datetime.now(timezone.utc)
    scope = await user_scope(db, user)
    since = _day_start(now) - timedelta(days=days - 1)
    previous = since - timedelta(days=days)
    messages = db[collections.MESSAGES_COLLECTION]

    # Questions and tokens per day of the window (days without a question are filled with zeros)
    per_day = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": since}, **scope}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "questions": {"$sum": 1},
            "prompt_tokens": {"$sum": {"$ifNull": ["$token_usage.prompt_tokens", 0]}},
            "completion_tokens": {"$sum": {"$ifNull": ["$token_usage.completion_tokens", 0]}},
            "flagged": {"$sum": {"$cond": [{"$eq": ["$user_rating", -1]}, 1, 0]}},
        }},
    ]).to_list(None)
    by_day = {row["_id"]: row for row in per_day}
    series = []
    for offset in range(days):
        day = (since + timedelta(days=offset)).strftime("%Y-%m-%d")
        row = by_day.get(day, {})
        series.append({
            "date": day,
            "questions": row.get("questions", 0),
            "prompt_tokens": row.get("prompt_tokens", 0),
            "completion_tokens": row.get("completion_tokens", 0),
            "flagged": row.get("flagged", 0),
        })

    by_model = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": since}, **scope}},
        {"$group": {"_id": "$model_used", "questions": {"$sum": 1}, "tokens": {"$sum": {"$ifNull": ["$token_usage.total_tokens", 0]}}}},
        {"$sort": {"tokens": -1}},
    ]).to_list(None)
    per_notebook = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": since}, **scope}},
        {"$group": {"_id": "$notebook_id", "tokens": {"$sum": {"$ifNull": ["$token_usage.total_tokens", 0]}}}},
    ]).to_list(None)
    notebook_owners = await _owner_labels(db, [row["_id"] for row in per_notebook])
    window_answers = await messages.find({"role": "assistant", "created_at": {"$gte": since}, **scope},
                                         {"trace_info.llm_calls": 1, "token_usage": 1, "created_at": 1, "notebook_id": 1, "model_used": 1}).to_list(None)
    prices = {"hit": settings.LLM_PRICE_HIT_PER_M, "miss": settings.LLM_PRICE_MISS_PER_M, "out": settings.LLM_PRICE_OUTPUT_PER_M}
    cost = cost_rows(window_answers, notebook_owners, prices)  # dollars at the configured prices (plan 26/11 3.1)
    for day in series:
        day["cost_usd"] = cost["per_day"].get(day["date"], 0.0)
    models = [{**row, "cost_usd": cost["by_model"].get(row["model"], 0.0)} for row in model_rows(by_model)]
    users_top = [{**row, "cost_usd": cost["by_user"].get(row["username"], 0.0)} for row in top_users(per_notebook, notebook_owners)]

    # Documents: count per status, then the newest with their processing job and owner
    documents = db[collections.DOCUMENTS_COLLECTION]
    status_rows = await documents.aggregate([{"$match": scope}, {"$group": {"_id": "$status", "count": {"$sum": 1}}}]).to_list(None)
    status_counts = {row["_id"]: row["count"] for row in status_rows}
    recent_docs = await documents.find(scope).sort("created_at", -1).limit(DOCUMENT_LIMIT).to_list(DOCUMENT_LIMIT)
    jobs = await db[collections.INGESTION_JOBS_COLLECTION].find(
        {"document_id": {"$in": [d["document_id"] for d in recent_docs]}}
    ).to_list(None)
    job_of = {j["document_id"]: j for j in jobs}
    doc_owners = await _owner_labels(db, [d["notebook_id"] for d in recent_docs])

    users = db[collections.USERS_COLLECTION]
    notebook_counts = await db[collections.NOTEBOOKS_COLLECTION].aggregate([
        {"$match": {"owner_type": "user"}}, {"$group": {"_id": "$owner_id", "count": {"$sum": 1}}}
    ]).to_list(None)
    notebooks_of = {row["_id"]: row["count"] for row in notebook_counts}
    user_rows = await users.find({}, {
        "user_id": 1, "username": 1, "email": 1, "full_name": 1, "role": 1, "is_active": 1, "total_tokens_consumed": 1,
        "created_at": 1, "last_login_at": 1,
    }).sort("total_tokens_consumed", -1).limit(USER_LIMIT).to_list(USER_LIMIT)

    return {
        "window_days": days,
        "user": user,
        "generated_at": now,
        "totals": {
            "current": await _window_totals(messages, since, now + timedelta(seconds=1), scope),
            "previous": await _window_totals(messages, previous, since, scope),
            "flagged_total": await messages.count_documents({"role": "assistant", "user_rating": -1, **scope}),
            "users_total": await users.count_documents({}),
            "users_active": await users.count_documents({"is_active": True}),
            "documents": {
                "total": sum(status_counts.values()),
                "ready": status_counts.get("ready", 0),
                "processing": status_counts.get("processing", 0) + status_counts.get("pending", 0),
                "failed": status_counts.get("failed", 0),
            },
        },
        "series": series,
        "by_model": models,
        "top_users": users_top,  # in the window, like the rest of the tokens page (U1, 26/11)
        "cost": {"total_usd": cost["total_usd"], "estimated_share": cost["estimated_share"], "prices": prices},
        "upload_times": upload_time_summary([job_times(j.get("timings") or {}) for j in jobs]),  # the listed uploads (O1, plan 3.3)
        "by_purpose": purpose_rows([a.get("trace_info") or {} for a in window_answers], prices),  # tokens, seconds, dollars per kind of model call (plan 3.2)
        "documents": [
            {
                "document_id": d["document_id"],
                "file_name": d.get("file_name"),
                "company": (d.get("metadata") or {}).get("company_name"),
                "ticker": (d.get("metadata") or {}).get("ticker"),
                "fiscal_year": (d.get("metadata") or {}).get("fiscal_year"),
                "report_type": (d.get("metadata") or {}).get("report_type"),
                "page_count": d.get("page_count", 0),
                "file_size_bytes": d.get("file_size_bytes", 0),
                "status": d.get("status"),
                "error_code": d.get("error_message"),
                "parsing_engine": d.get("parsing_engine"),
                "parse_issues": d.get("parse_issues") or {},  # pages the user is told to check (ingestion/parse_check.py)
                "stage": job_of.get(d["document_id"], {}).get("stage"),
                "progress_percent": job_of.get(d["document_id"], {}).get("progress_percent"),
                "chunks": job_of.get(d["document_id"], {}).get("extracted_chunks_count"),
                "duration_s": (job_of.get(d["document_id"], {}).get("timings") or {}).get("total"),
                **job_times(job_of.get(d["document_id"], {}).get("timings") or {}),  # wait_s / work_s: the wait for a parse slot is not work (O1)
                # how the reading went (plan 24/11, channel D): pages read again, refused and why
                "read_report": {k: v for k, v in (job_of.get(d["document_id"], {}).get("timings") or {}).items()
                                if k in ("ocr_bad_pages", "ocr_replaced_pages", "ocr_rejected")},
                "created_at": d.get("created_at"),
                **doc_owners.get(d["notebook_id"], {"owner_type": "unknown", "username": None, "notebook_title": None}),
            }
            for d in recent_docs
        ],
        "flagged": await _answers(db, {"user_rating": -1, **scope}, FLAGGED_LIMIT, newest_by="rated_at"),
        "recent_answers": await _answers(db, {"created_at": {"$gte": since}, **scope}, MESSAGE_LIMIT),
        "users": [
            {
                "user_id": u["user_id"],
                "username": u.get("username"),
                "email": u.get("email"),
                "full_name": u.get("full_name"),
                "role": u.get("role", "user"),
                "is_active": u.get("is_active", True),
                "total_tokens": u.get("total_tokens_consumed", 0),
                "notebooks": notebooks_of.get(u["user_id"], 0),
                "created_at": u.get("created_at"),
                "last_login_at": u.get("last_login_at"),
            }
            for u in user_rows
        ],
    }
