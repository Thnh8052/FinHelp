"""The admin review queue (owner 19/11): every answer with a problem reaches the admin on its own, not only the ones a user reported. Each problem is
one MongoDB condition on what the chat already stores with an answer (its trace); the queue's query and each answer's labels both come from PROBLEMS, so
they cannot disagree. An admin marks an answer reviewed ("ok" or "needs_fix", with a note); it then leaves the open queue."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.infrastructure.database import collections
from app.modules.admin.overview import _answers, _day_start, user_scope  # noqa: F401  (user_scope: the dashboard's user filter)

SLOW_MS = 60_000  # 4 of 124 dev answers with a model call took longer (p90 40 s)
# Turned away by the code checks before any search: a wrong one hides a question the reports answer (B8 refused 2 answerable gold questions this way)
INPUT_REFUSALS = ["period_unavailable", "form_unavailable", "out_of_scope", "empty_plan", "not_supported_yet", "refuse_concept", "refuse_out_of_domain",
                  "unsupported_language", "ask_clarify"]
# Turned away for safety (the guard or the rules): a wrong one blocks a legitimate question (measured 17/11: 6 of 352)
SAFETY_REPLIES = ["refuse_advice", "refuse_sensitive", "refuse_instruction", "refuse_political", "support"]

PROBLEMS: Dict[str, Dict[str, Any]] = {
    "user_report": {"user_rating": -1},  # the user pressed "Report wrong figures"
    # a figure, calculation or citation the checks could not trace: kept in the trace, never shown to the user (owner 19/11), so the admin looks
    "not_traced": {"trace_info.verification.passed": False},
    "blocked": {"trace_info.review.outcome": "blocked"},  # replaced by the fixed reply of the safety check
    "not_found": {"trace_info.answer_meta.status": "not_found"},
    "partial": {"trace_info.answer_meta.status": "partial"},
    "degraded": {"trace_info.degraded.0": {"$exists": True}},  # a step was dropped because it was too slow
    "refused": {"trace_info.intent": {"$in": INPUT_REFUSALS}},
    "safety": {"trace_info.intent": {"$in": SAFETY_REPLIES}},
    "slow": {"latency_ms": {"$gt": SLOW_MS}},
}
LABELS = list(PROBLEMS)
REVIEW_STATES = ("ok", "needs_fix")
QUEUE_LIMIT = 200


def _get(doc: Any, path: str) -> Any:
    node = doc
    for key in path.split("."):
        if isinstance(node, list) and key.isdigit():
            node = node[int(key)] if int(key) < len(node) else _MISSING
        elif isinstance(node, dict):
            node = node.get(key, _MISSING)
        else:
            return _MISSING
    return node


_MISSING = object()


def matches(query: Dict[str, Any], doc: Dict[str, Any]) -> bool:
    """The MongoDB operators the review filters use ($or, $and, $in, $nin, $gt, $gte, $lt, $exists, equality, dotted paths), read in Python: the labels
    of an answer are the conditions it meets."""
    for key, cond in query.items():
        if key == "$or":
            if not any(matches(c, doc) for c in cond):
                return False
            continue
        if key == "$and":
            if not all(matches(c, doc) for c in cond):
                return False
            continue
        value = _get(doc, key)
        if isinstance(cond, dict) and any(k.startswith("$") for k in cond):
            for op, arg in cond.items():
                ok = {"$in": lambda: value is not _MISSING and value in arg,
                      "$nin": lambda: value is _MISSING or value not in arg,
                      "$gt": lambda: value is not _MISSING and value is not None and value > arg,
                      "$gte": lambda: value is not _MISSING and value is not None and value >= arg,
                      "$lt": lambda: value is not _MISSING and value is not None and value < arg,
                      "$exists": lambda: (value is not _MISSING) == bool(arg)}[op]()
                if not ok:
                    return False
        elif value is _MISSING or value != cond:
            return False
    return True


def problem_labels(doc: Dict[str, Any]) -> List[str]:
    return [label for label, cond in PROBLEMS.items() if matches(cond, doc)]


def _state(status: str) -> Dict[str, Any]:
    return {"admin_review": {"$exists": False}} if status == "open" else {"admin_review": {"$exists": True}} if status == "reviewed" else {}


PAGE_FLAGS = ("may_be_misread", "read_from_image", "from_figure", "picture_unread")  # the citation flags set from the page checks at upload


def flagged_pages(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The pages an answer cites that were read with a problem at upload, one entry per page with its flags (owner 25/11): the admin sees at once
    whether a reported figure may come from the reading of the PDF rather than from the answer. An excerpt the answer does not cite is left out."""
    out: Dict[tuple, List[str]] = {}
    for c in doc.get("citations") or []:
        flags = [f for f in PAGE_FLAGS if c.get(f)]
        if flags and c.get("cited") is not False:
            seen = out.setdefault((c.get("document_id"), c.get("page")), [])
            seen += [f for f in flags if f not in seen]
    return [{"document_id": d, "page": p, "flags": f} for (d, p), f in out.items()]


def _extra(doc: Dict[str, Any]) -> Dict[str, Any]:
    trace = doc.get("trace_info") or {}
    return {"labels": problem_labels(doc), "review": doc.get("admin_review"), "intent": trace.get("intent"), "flagged_pages": flagged_pages(doc),
            "status": (trace.get("answer_meta") or {}).get("status"), "unverified": (trace.get("verification") or {}).get("unverified_figures") or [],
            "notes": trace.get("notes") or [], "degraded": trace.get("degraded") or []}


def _open(base: Dict[str, Any]) -> Dict[str, Any]:
    return {**base, "$and": [{"$or": list(PROBLEMS.values())}, _state("open")]}


async def open_count(db, days: int = 14, user: Optional[str] = None, now: Optional[datetime] = None) -> int:
    """How many answers wait in the open queue (the badge of the dashboard's menu)."""
    now = now or datetime.now(timezone.utc)
    base = {"role": "assistant", "created_at": {"$gte": _day_start(now) - timedelta(days=days - 1)}, **await user_scope(db, user)}
    return await db[collections.MESSAGES_COLLECTION].count_documents(_open(base))


async def review_queue(db, days: int = 14, label: Optional[str] = None, user: Optional[str] = None, status: str = "open", limit: int = QUEUE_LIMIT,
                       now: Optional[datetime] = None) -> Dict[str, Any]:
    """The problem answers of the last `days` days, newest first: `label` narrows to one problem, `user` to one user (or "guests"), `status` is
    open | reviewed | all. `counts` are the open answers per problem in the same window and scope, for the filter chips."""
    now = now or datetime.now(timezone.utc)
    base = {"role": "assistant", "created_at": {"$gte": _day_start(now) - timedelta(days=days - 1)}, **await user_scope(db, user)}
    problems = [PROBLEMS[label]] if label in PROBLEMS else list(PROBLEMS.values())
    query = {**base, "$and": [{"$or": problems}, _state(status)]}
    messages = db[collections.MESSAGES_COLLECTION]
    counts = {name: await messages.count_documents({**base, **cond, **_state("open")}) for name, cond in PROBLEMS.items()}
    open_total = await messages.count_documents(_open(base))
    items = await _answers(db, {k: v for k, v in query.items() if k != "role"}, min(limit, QUEUE_LIMIT), extra=_extra)
    ids = list({p["document_id"] for i in items for p in i["flagged_pages"]})
    names = {d["document_id"]: d.get("file_name") for d in await db[collections.DOCUMENTS_COLLECTION].find(
        {"document_id": {"$in": ids}}, {"document_id": 1, "file_name": 1}).to_list(None)} if ids else {}
    for i in items:
        for p in i["flagged_pages"]:
            p["file_name"] = names.get(p["document_id"])  # None once the document was deleted
    return {"items": items, "counts": counts, "open_total": open_total, "window_days": days}


async def set_review(db, message_id: str, status: str, note: str, reviewer: str, now: Optional[datetime] = None) -> bool:
    """Marks an answer reviewed ("ok" | "needs_fix", with a note), or open again ("open"). False when there is no such answer."""
    messages = db[collections.MESSAGES_COLLECTION]
    if status == "open":
        update = {"$unset": {"admin_review": ""}}
    else:
        update = {"$set": {"admin_review": {"status": status, "note": (note or "").strip()[:2000], "by": reviewer, "at": now or datetime.now(timezone.utc)}}}
    result = await messages.update_one({"message_id": message_id, "role": "assistant"}, update)
    return result.matched_count == 1
