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
import uuid
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple
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

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])

MAX_QUERY_CHARS = 4000


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
    alternatives: List[dict] = []  # other selected documents that also match: [{"document_id", "label"}]


class MessageOut(BaseModel):
    """A stored message as the interface shows it: of its trace, only how the question was understood."""

    message_id: str
    notebook_id: str
    role: str
    content: str
    citations: List[CitationOut]
    understood: str
    alternatives: List[dict]
    created_at: Any

    @classmethod
    def of(cls, message: MessageRecord) -> "MessageOut":
        trace = message.trace_info or {}
        return cls(**message.model_dump(exclude={"trace_info"}), understood=trace.get("understood") or "", alternatives=trace.get("alternatives") or [])


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


async def _admit(request: Request, req: "QueryRequest", user_id: Optional[str], db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient) -> _Admitted:
    """Every refusal comes here, before the answer starts (a plain JSON error, nothing charged or written), then the quota is reserved."""
    # 0. Tài liệu phải xử lý xong mới truy vấn được; chặn trước khi trừ hạn mức
    nb = await require_notebook(db, req.notebook_id, user_id)
    if not can_chat(nb, user_id):  # past require_notebook, only a read-only sample notebook is refused: signing in does not change that
        raise api_error(status_code=403, code=Code.SAMPLE_NOTEBOOK_READ_ONLY)
    chosen, mentions = validate_question(req.document_ids, req.document_id, req.mentions, req.query, signed_in=user_id is not None)
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
    return _Admitted(nb, chosen, mentions, orchestrator, history, users)


async def _answered(adm: _Admitted, req: "QueryRequest", user_id: Optional[str]) -> dict:
    """3. Kích hoạt RAG Workflow Orchestrator; không có câu trả lời thì trả lại lượt đã giữ."""
    try:
        return await adm.orchestrator.execute_query(
            query=req.query,
            notebook_id=req.notebook_id,
            document_ids=adm.chosen,
            history=adm.history,
            mentions=adm.mentions,
            focus_state=adm.nb.focus_state,
        )
    except BaseException:  # a cancelled answer too
        if user_id is not None:
            await adm.users.consume_quota(user_id, messages=-1)
        raise


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
    await chat_repo.append_message(
        MessageRecord(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
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
    return [MessageOut.of(m) for m in await ChatRepository(db).get_messages(notebook_id)]
