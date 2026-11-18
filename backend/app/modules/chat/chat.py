"""
API Router: Hỏi Đáp RAG Tài Chính (Financial RAG Chat)
Tác giả: Vũ Thành - FinAnalyst AI

Mỗi notebook là một đoạn chat.
1. Tiếp nhận câu hỏi tài chính từ người dùng (POST /api/v1/chat/query).
2. Hỗ trợ 2 chế độ:
   - Chưa đăng nhập (Guest): Hỏi trong notebook khách của mình, giới hạn số câu mỗi ngày theo địa chỉ IP (chỉ 1 tài liệu nguồn).
   - Đã đăng nhập (User): Có hạn mức câu hỏi mỗi ngày.
3. Lưu tin nhắn người dùng và phản hồi của trợ lý AI (kèm citations, token, độ trễ) vào MongoDB.
4. Lấy lịch sử hội thoại của một notebook (GET /api/v1/chat/messages/{notebook_id}).
"""

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, List, Literal, Optional, Tuple, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.shared.deps import can_chat, get_optional_user_id, require_notebook
from app.shared.rate_limit import spend_guest_allowance
from app.core.error_codes import Code, api_error
from app.core.config import settings
from app.core.exceptions import DomainException
from app.core.logging import logger
from app.modules.chat import events
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.chat.chat_repo import ChatRepository
from app.modules.documents.document import ACTIVE_STATUSES
from app.modules.documents.document_repo import DocumentRepository
from app.modules.auth.user_repo import UserRepository
from app.modules.chat.chat_models import MessageRecord
from app.modules.notebooks.notebook import UNTITLED, shown_title, title_from_question
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator, SourceSelectionError
from app.modules.query_router.input_policy import MAX_QUESTION_CHARS

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])

MAX_QUERY_CHARS = MAX_QUESTION_CHARS


def selected_ids(document_ids: Optional[List[str]], document_id: Optional[str]) -> List[str]:
    """The sources chosen by the user: the list, or the single id of older clients."""
    return list(dict.fromkeys(document_ids or ([document_id] if document_id else [])))


def validate_question(document_ids: Optional[List[str]], document_id: Optional[str], mentions: Optional[List[str]], query: str,
                      signed_in: bool) -> Tuple[List[str], List[str]]:
    """(chosen sources, @-tagged sources) of a question, or 422 before anything is stored or charged. The chat and the admin
    inspector both check a question here."""
    chosen = selected_ids(document_ids, document_id)
    limit = settings.MAX_SELECTED_DOCS_USER if signed_in else settings.MAX_SELECTED_DOCS_GUEST
    if not chosen:
        raise api_error(status_code=422, code=Code.NO_SOURCE_SELECTED)
    if len(chosen) > limit:
        raise api_error(status_code=422, code=Code.TOO_MANY_SOURCES, max=limit)
    tagged = list(dict.fromkeys(mentions or []))
    if any(m not in chosen for m in tagged):
        raise api_error(status_code=422, code=Code.MENTION_NOT_SELECTED)
    if len(query) > MAX_QUERY_CHARS:  # the input policy has the same limit
        raise api_error(status_code=422, code=Code.QUESTION_TOO_LONG, max=MAX_QUERY_CHARS)
    return chosen, tagged


async def load_history(db: AsyncIOMotorDatabase, notebook_id: str) -> List[dict]:
    """The last turns of the conversation, so that a follow-up ("and the net income?") can be understood."""
    return [{"role": m.role, "content": m.content, "citations": [c.model_dump() for c in m.citations]}
            for m in await ChatRepository(db).get_messages(notebook_id, limit=6)]


async def ensure_documents_ready(db: AsyncIOMotorDatabase, notebook_id: str, document_ids: List[str]) -> None:
    """Strict chat gating: 409 while ANY document of the notebook is still being processed (a failed one does not block);
    422 if a selected document is unknown or failed."""
    docs = {d.document_id: d for d in await DocumentRepository(db).get_by_notebook(notebook_id)}
    if any(i not in docs for i in document_ids):
        raise api_error(status_code=422, code=Code.SOURCE_NOT_IN_NOTEBOOK)
    if any(d.status in ACTIVE_STATUSES for d in docs.values()):
        raise api_error(status_code=409, code=Code.DOCUMENTS_BUSY)
    if any(docs[i].status == "failed" for i in document_ids):
        raise api_error(status_code=422, code=Code.SOURCE_FAILED)


# --- Schemas ---

class QueryRequest(BaseModel):
    notebook_id: str
    query: str
    document_id: Optional[str] = None  # one source (older clients)
    document_ids: Optional[List[str]] = None  # the sources selected by the user (at least one)
    mentions: Optional[List[str]] = None  # @file: selected documents the question is explicitly about (ids, never parsed from the text)
    retry_of: Optional[str] = None  # sent by a "search again" button: the answer that fell short (docs/Version_3/fail_cases.md, S3)
    deeper: bool = False  # with retry_of: the "search deeper" button (same documents, the excerpts already sent left out); without: the document chooser
    again: bool = False  # with retry_of: the "try again" button after a model that could not be reached (same documents, same search, nothing left out)
    everywhere: bool = False  # with retry_of: the "search all sources" button after an empty plan (every source of that answer, each tagged: the full pipeline)
    ui_lang: Optional[Literal["vi", "en"]] = None  # the interface language: the reply to a message too short to show its own ("?")


class CitationOut(BaseModel):
    """An excerpt as the interface shows it: no chunk ids or search scores."""

    citation_id: str
    document_id: str
    page: int
    snippet: str
    cited: Optional[bool] = None


class QueryResponse(BaseModel):
    title: str  # the notebook's title: named after the first question
    query: str
    answer: str
    citations: List[CitationOut]
    understood: str = ""  # G3: how the question was understood (documents, assumptions), shown above the answer
    alternatives: List[dict] = []  # buttons of answers stored before 17/11/2026 ([{"document_id", "label", "kind"?}]); new answers carry `actions`
    actions: dict = {}  # {"chooser": [{"document_id", "label", "checked"}], "search_more": {"prominent"} | None, "edit_question", "try_again", "search_all"?} (orchestrator.answer_actions, empty_plan_reply)
    message_id: str = ""  # the stored answer: what a report of wrong figures points to


class MessageOut(BaseModel):
    """A stored message as the interface shows it: of its trace, only how the question was understood."""

    message_id: str
    notebook_id: str
    role: str
    content: str
    citations: List[CitationOut]
    understood: str
    alternatives: List[dict]
    actions: dict = {}
    created_at: Any
    user_rating: Optional[int] = None  # -1: the user reported wrong figures
    click: str = ""  # this answer was asked by a button: "deeper" | "again" | "chooser" | "everywhere" | "retry" (older, kind unknown) (tests/test_click_marks.py)
    clicked: str = ""  # a button was used on this answer: which one (its answer follows)

    @classmethod
    def of(cls, message: MessageRecord) -> "MessageOut":
        trace = message.trace_info or {}
        return cls(**message.model_dump(exclude={"trace_info"}), understood=trace.get("understood") or "", alternatives=trace.get("alternatives") or [],
                   actions=trace.get("actions") or {}, click=click_of(trace))


def click_of(trace: dict) -> str:
    """Which button asked this answer ("" for a typed question). Answers stored before 18/11/2026 kept only retry_of: "retry", a neutral mark (either button)."""
    return (trace.get("click") or "retry") if trace.get("retry_of") else ""


# --- Endpoints ---

@dataclass
class _Admitted:
    """A question past every check, its quota reserved: what answering and recording it need."""

    nb: Any
    chosen: List[str]
    mentions: List[str]
    orchestrator: RAGWorkflowOrchestrator
    history: List[dict]
    users: UserRepository
    retry_of: Optional[MessageRecord] = None  # the answer a "search again" button asks for once more


async def retried_message(chat_repo: Any, notebook_id: str, retry_of: Optional[str]) -> Optional[MessageRecord]:
    """The answer of this notebook a "search again" click points to (None: an ordinary question); any other id is refused with 404. One click only:
    an answer already searched again, or the answer of a click itself, is refused with 409."""
    if not retry_of:
        return None
    messages = await chat_repo.get_messages(notebook_id)
    found = next((m for m in messages if m.message_id == retry_of and m.role == "assistant"), None)
    if found is None:
        raise api_error(status_code=404, code=Code.MESSAGE_NOT_FOUND)
    if (found.trace_info or {}).get("retry_of") or retry_of in _retried(messages):
        raise api_error(status_code=409, code=Code.RETRY_USED)
    return found


def deeper_of(message: MessageRecord) -> Dict[str, List[str]]:
    """What a "search deeper" click on `message` leaves out (every excerpt it sent: the trace's chunk_ids, else its citations) and keeps (the ones it cited)."""
    sent = [c.chunk_id for c in message.citations if c.chunk_id]
    return {"exclude": list((message.trace_info or {}).get("chunk_ids") or sent), "keep": [c.chunk_id for c in message.citations if c.cited and c.chunk_id]}


def uses_answer_documents(req: "QueryRequest") -> bool:
    """A click that asks again over the documents of the clicked answer ("search deeper", "try again", "search all sources"), not over the ones it sends
    (the chooser's ticks)."""
    return req.retry_of is not None and (req.deeper or req.again or req.everywhere)


def click_documents(req: "QueryRequest", message: MessageRecord, chosen: List[str], mentions: List[str]) -> Tuple[List[str], List[str]]:
    """The sources and @ tags a click on `message` asks over. "Search all sources" tags every source of that answer: code then searches them even when the
    planner again chooses none (retrieval_step: a targeted empty plan is vetoed)."""
    if not uses_answer_documents(req):
        return chosen, mentions
    chosen, mentions = same_documents(message, chosen, mentions)
    return (chosen, list(chosen)) if req.everywhere else (chosen, mentions)


def same_documents(message: MessageRecord, chosen: List[str], mentions: List[str]) -> Tuple[List[str], List[str]]:
    """The sources and @ tags a "search deeper" click on `message` searches: the ones that answer was asked over (trace "asked"), whatever the sidebar
    shows now; an answer stored before the trace kept them keeps the request's choice."""
    asked = (message.trace_info or {}).get("asked") or {}
    return (list(asked["document_ids"]), list(asked.get("mentions") or [])) if asked.get("document_ids") else (chosen, mentions)


def _retried(messages: List[MessageRecord]) -> set:
    """The answers a "search again" click was already used on."""
    return {(m.trace_info or {}).get("retry_of") for m in messages} - {None}


def shown_messages(messages: List[MessageRecord]) -> List["MessageOut"]:
    """The stored messages as the interface shows them: an answer already searched again keeps no "search again" button (one click)."""
    used = _retried(messages)
    out = [MessageOut.of(m) for m in messages]
    clicks = {(m.trace_info or {}).get("retry_of"): click_of(m.trace_info or {}) for m in messages if (m.trace_info or {}).get("retry_of")}
    for m in out:
        if m.message_id in used:
            m.clicked = clicks.get(m.message_id, "")
            m.alternatives = [a for a in m.alternatives if not a.get("kind")]
            if m.actions:
                m.actions = {**m.actions, "chooser": [], "search_more": None, "try_again": False, "search_all": False}
    return out


async def _admit(request: Request, req: "QueryRequest", user_id: Optional[str], db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient) -> _Admitted:
    """Every refusal comes here, before the answer starts (a plain JSON error, nothing charged or written), then the quota is reserved."""
    # 0. Tài liệu phải xử lý xong mới truy vấn được; chặn trước khi trừ hạn mức
    nb = await require_notebook(db, req.notebook_id, user_id)
    if not can_chat(nb, user_id):  # past require_notebook, only a read-only sample notebook is refused: signing in does not change that
        raise api_error(status_code=403, code=Code.SAMPLE_NOTEBOOK_READ_ONLY)
    chosen, mentions = validate_question(req.document_ids, req.document_id, req.mentions, req.query, signed_in=user_id is not None)
    retry_of = await retried_message(ChatRepository(db), req.notebook_id, req.retry_of)
    if retry_of is not None:  # a click asks over the documents of the clicked answer (or the chooser's ticks), checked below like any choice
        chosen, mentions = click_documents(req, retry_of, chosen, mentions)
    await ensure_documents_ready(db, req.notebook_id, chosen)
    orchestrator = RAGWorkflowOrchestrator(db, qdrant)
    try:  # a question without a usable source choice is refused before it costs quota or writes a message
        await orchestrator.resolve_scope(req.notebook_id, chosen)
    except SourceSelectionError as exc:
        raise api_error(status_code=422, code=exc.code, **exc.params)

    # 1. Các lượt trước (để hiểu câu hỏi nối tiếp như "còn lợi nhuận thì sao?")
    history = await load_history(db, req.notebook_id)

    # 2. Giữ chỗ hạn mức ngay trước pipeline, không phải sau: các câu gửi cùng lúc không thể cùng thấy "còn lượt"
    users = UserRepository(db)
    if user_id is None:
        spend_guest_allowance(request, "question", settings.GUEST_DAILY_QUESTIONS)
    elif not await users.reserve_quota(user_id):
        raise api_error(status_code=429, code=Code.QUESTION_QUOTA_USED)
    return _Admitted(nb, chosen, mentions, orchestrator, history, users, retry_of)


_UNDERSTOOD_LINE = re.compile(r"(?:Tôi hiểu câu hỏi là|I understood the question as): “.*?”\n\n", re.S)


def follow_up_of(req: "QueryRequest", message: Optional[MessageRecord]) -> Optional[dict]:
    """The trace of how the clicked answer understood its question ({"method", "resolved"}), when that question was a follow-up ("And the net income?")
    and the click asks the same question again ("search deeper", "try again", "search all sources"). Such a click must ask the question as it was
    understood then: sent as the original words, the follow-up is understood a second time against the conversation as it is now, many turns later,
    and another question gets searched (system test 18/11, B1)."""
    if message is None or not uses_answer_documents(req):
        return None
    followup = (message.trace_info or {}).get("followup") or {}
    return followup if followup.get("resolved") else None


async def _answered(adm: _Admitted, req: "QueryRequest", user_id: Optional[str]) -> dict:
    """3. Kích hoạt RAG Workflow Orchestrator; không có câu trả lời thì trả lại lượt đã giữ."""
    followup = follow_up_of(req, adm.retry_of)
    try:
        result = await adm.orchestrator.execute_query(
            query=followup["resolved"] if followup else req.query,
            notebook_id=req.notebook_id,
            document_ids=adm.chosen,
            history=[] if followup else adm.history,  # a standalone question needs no conversation (as after the first understanding: decide(resolved, ..., []))
            mentions=adm.mentions,
            focus_state={} if followup else adm.nb.focus_state,
            retry=adm.retry_of is not None,
            ui_lang=req.ui_lang,
            **({"deeper": deeper_of(adm.retry_of)} if req.deeper and adm.retry_of is not None else {}),
        )
    except BaseException:  # a cancelled answer too
        if user_id is not None:
            await adm.users.consume_quota(user_id, messages=-1)
        raise
    result.setdefault("trace", {})["asked"] = {"document_ids": list(adm.chosen), "mentions": list(adm.mentions)}  # what "search deeper" searches again
    if followup:  # the answer says how the question was understood, as the first one did
        result["trace"]["followup"] = followup
        said = _UNDERSTOOD_LINE.match(adm.retry_of.content)
        if said:
            result["answer"] = said.group(0) + result["answer"]
    if adm.retry_of is not None:
        result["trace"]["retry_of"] = adm.retry_of.message_id
        result["trace"]["click"] = ("deeper" if req.deeper else "again" if req.again else "everywhere" if req.everywhere else "chooser")  # the interface marks the click and its answer
    return result


async def _record(adm: _Admitted, req: "QueryRequest", user_id: Optional[str], db: AsyncIOMotorDatabase, result: dict) -> "QueryResponse":
    chat_repo = ChatRepository(db)
    nb, users = adm.nb, adm.users
    # 4. Câu hỏi chỉ được lưu khi đã có câu trả lời: câu hỏi lỗi không kẹt lại trong lịch sử và ngữ cảnh. Câu hỏi đầu tiên
    # được tìm trong tài liệu đặt tên cho đoạn chat (câu chào hay câu bị từ chối thì không)
    title = nb.title
    if nb.title in UNTITLED and result.get("charged", True):
        title = title_from_question(req.query)
        await chat_repo.set_title(req.notebook_id, title)
    await chat_repo.append_message(
        MessageRecord(message_id=f"msg_{uuid.uuid4().hex[:8]}", notebook_id=req.notebook_id, role="user", content=req.query)
    )

    # Người dùng đã đăng nhập: lượt hỏi đã được giữ ở bước 2; câu không thật sự tìm và sinh câu trả lời
    # (từ chối, câu chào, lệnh liệt kê nguồn, hỏi lại...) được trả lại lượt; token thì luôn ghi đúng lượng đã dùng
    trace = result.get("trace", {})
    llm = trace.get("llm", {})
    prompt_tokens, completion_tokens = llm.get("prompt_tokens", 0), llm.get("completion_tokens", 0)
    if user_id is not None:
        await users.consume_quota(user_id, messages=0 if result.get("charged", True) else -1, tokens=prompt_tokens + completion_tokens)

    # 5. Lưu câu trả lời của AI kèm trích dẫn và số liệu thực nghiệm vào MongoDB
    answer_id = f"msg_{uuid.uuid4().hex[:8]}"
    await chat_repo.append_message(
        MessageRecord(
            message_id=answer_id,
            notebook_id=req.notebook_id,
            role="assistant",
            content=result["answer"],
            citations=result["citations"],
            trace_info={**trace, "intent": result["intent"], "router": trace.get("intent")},  # the router's verdict has the same key in the trace
            token_usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
            latency_ms=round(trace.get("timings", {}).get("total", 0) * 1000),
            model_used=settings.DEFAULT_LLM_MODEL if llm.get("calls") else None,
        )
    )
    if result.get("focus"):  # only once the answer is stored: a failed question cannot move the topic
        await chat_repo.set_focus(req.notebook_id, result["focus"])

    return QueryResponse(
        title=shown_title(title),
        query=req.query,
        answer=result["answer"],
        citations=result["citations"],
        understood=result.get("understood", ""),
        alternatives=result.get("alternatives", []),
        actions=result.get("actions", {}),
        message_id=answer_id,
    )


# ==============================================================================
# HÀM: handle_user_query
# Ý NGHĨA: Điểm đầu vào chính của quy trình hỏi đáp tài chính RAG:
#          1. Kiểm tra quyền truy cập notebook, nguồn tài liệu đã chọn và hạn mức.
#          2. Kích hoạt Orchestrator điều phối pipeline tìm kiếm ngữ nghĩa và sinh câu trả lời.
#          3. Ghi nhận hạn mức, lưu câu hỏi, câu trả lời kèm trích dẫn và số liệu (token, độ trễ, model).
# ==============================================================================
@router.post("/query", response_model=QueryResponse)
async def handle_user_query(
    request: Request,
    req: QueryRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Xử lý câu hỏi tài chính, thực thi luồng RAG và lưu lịch sử vào MongoDB."""
    adm = await _admit(request, req, user_id, db, qdrant)
    result = await _answered(adm, req, user_id)
    return await _record(adm, req, user_id, db, result)


_RUNNING: set = set()  # answers still being written after their page was closed: referenced until they are recorded


def _sse(kind: str, data: dict) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/query/stream")
async def stream_user_query(
    request: Request,
    req: QueryRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """The question of /query answered as server-sent events (chat/events.py): stage, understood, delta (the answer as it is written),
    then done (the recorded answer: the body of /query, which replaces the streamed text) or error ({status, code, params}).
    Refusals before the answer starts stay ordinary JSON errors. An answer whose page was closed is still written and recorded: it is in
    the history when the chat is opened again."""
    adm = await _admit(request, req, user_id, db, qdrant)
    stream = events.ChatStream()

    async def run() -> None:
        events.attach(stream)
        try:
            result = await _answered(adm, req, user_id)
            stream.emit("done", (await _record(adm, req, user_id, db, result)).model_dump(mode="json"))
        except DomainException as exc:
            stream.emit("error", {"status": exc.status_code, "code": exc.code, "params": exc.params})
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            stream.emit("error", {"status": exc.status_code, "code": detail.get("code", Code.INTERNAL_ERROR), "params": detail.get("params", {})})
        except Exception:
            logger.exception(f"Streamed question failed in notebook {req.notebook_id}")
            stream.emit("error", {"status": 500, "code": Code.INTERNAL_ERROR, "params": {}})
        finally:
            stream.close()

    task = asyncio.create_task(run())
    _RUNNING.add(task)
    task.add_done_callback(_RUNNING.discard)

    async def body():
        yield _sse("stage", {"name": "understanding"})
        while True:
            kind, data = await stream.queue.get()
            if kind is None:
                return
            yield _sse(kind, data)

    # no-cache and X-Accel-Buffering: a proxy in front must pass each event on at once, not hold the answer back until it ends
    return StreamingResponse(body(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ==============================================================================
# HÀM: get_messages
# Ý NGHĨA: Lấy lịch sử tin nhắn của một notebook để Frontend hiển thị lại đoạn chat.
# ==============================================================================
@router.get("/messages/{notebook_id}", response_model=List[MessageOut])
async def get_messages(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy các tin nhắn mới nhất của một notebook, theo đúng thứ tự hội thoại."""
    await require_notebook(db, notebook_id, user_id)
    return shown_messages(await ChatRepository(db).get_messages(notebook_id))


class FlagRequest(BaseModel):
    flagged: bool  # True: the answer has wrong figures; False: the report is withdrawn


# ==============================================================================
# HÀM: flag_answer
# Ý NGHĨA: Người dùng báo một câu trả lời sai số liệu (hoặc rút lại); Admin xem các câu bị báo ở /admin để kiểm duyệt.
# ==============================================================================
@router.put("/messages/{notebook_id}/{message_id}/flag")
async def flag_answer(
    notebook_id: str,
    message_id: str,
    req: FlagRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Whoever may ask in the notebook may report its answers: the owner, or the guest of a guest notebook."""
    nb = await require_notebook(db, notebook_id, user_id)
    if not can_chat(nb, user_id):
        raise api_error(status_code=403, code=Code.SAMPLE_NOTEBOOK_READ_ONLY)
    if not await ChatRepository(db).set_rating(notebook_id, message_id, -1 if req.flagged else None):
        raise api_error(status_code=404, code=Code.MESSAGE_NOT_FOUND)
    return {"flagged": req.flagged}
