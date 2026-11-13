"""Read-only numbers for the admin dashboard (GET /auth/admin/overview): questions and tokens per day, the processing state of every
recent PDF, the answers users marked wrong, recent answers for audit and the user list. One request feeds every page of the dashboard."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.infrastructure.database import collections

DOCUMENT_LIMIT = 100
MESSAGE_LIMIT = 100
FLAGGED_LIMIT = 50
USER_LIMIT = 200
ANSWER_PREVIEW_CHARS = 3000


def _day_start(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


async def _window_totals(messages, start: datetime, end: datetime) -> Dict[str, Any]:
    rows = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": start, "$lt": end}}},
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


async def _answers(db: AsyncIOMotorDatabase, query: Dict[str, Any], limit: int, newest_by: str = "created_at") -> List[Dict[str, Any]]:
    """Assistant answers matching `query`, newest first by `newest_by`, each with the question asked just before it and who asked."""
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
        }
        for a in answers
    ]


async def build_overview(db: AsyncIOMotorDatabase, days: int) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = _day_start(now) - timedelta(days=days - 1)
    previous = since - timedelta(days=days)
    messages = db[collections.MESSAGES_COLLECTION]

    # Questions and tokens per day of the window (days without a question are filled with zeros)
    per_day = await messages.aggregate([
        {"$match": {"role": "assistant", "created_at": {"$gte": since}}},
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
        {"$match": {"role": "assistant", "created_at": {"$gte": since}}},
        {"$group": {"_id": "$model_used", "questions": {"$sum": 1}, "tokens": {"$sum": {"$ifNull": ["$token_usage.total_tokens", 0]}}}},
        {"$sort": {"tokens": -1}},
    ]).to_list(None)

    # Documents: count per status, then the newest with their processing job and owner
    documents = db[collections.DOCUMENTS_COLLECTION]
    status_rows = await documents.aggregate([{"$group": {"_id": "$status", "count": {"$sum": 1}}}]).to_list(None)
    status_counts = {row["_id"]: row["count"] for row in status_rows}
    recent_docs = await documents.find({}).sort("created_at", -1).limit(DOCUMENT_LIMIT).to_list(DOCUMENT_LIMIT)
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
        "generated_at": now,
        "totals": {
            "current": await _window_totals(messages, since, now + timedelta(seconds=1)),
            "previous": await _window_totals(messages, previous, since),
            "flagged_total": await messages.count_documents({"role": "assistant", "user_rating": -1}),
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
        "by_model": [{"model": row["_id"] or "unknown", "questions": row["questions"], "tokens": row["tokens"]} for row in by_model],
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
                "stage": job_of.get(d["document_id"], {}).get("stage"),
                "progress_percent": job_of.get(d["document_id"], {}).get("progress_percent"),
                "chunks": job_of.get(d["document_id"], {}).get("extracted_chunks_count"),
                "duration_s": (job_of.get(d["document_id"], {}).get("timings") or {}).get("total"),
                "created_at": d.get("created_at"),
                **doc_owners.get(d["notebook_id"], {"owner_type": "unknown", "username": None, "notebook_title": None}),
            }
            for d in recent_docs
        ],
        "flagged": await _answers(db, {"user_rating": -1}, FLAGGED_LIMIT, newest_by="rated_at"),
        "recent_answers": await _answers(db, {"created_at": {"$gte": since}}, MESSAGE_LIMIT),
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
