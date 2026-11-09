"""
API Router: Hỏi Đáp RAG Tài Chính (Financial RAG Chat)
Tác giả: Vũ Thành - FinAnalyst AI

Mỗi notebook là một đoạn chat.
1. Tiếp nhận câu hỏi tài chính từ người dùng (POST /api/v1/chat/query).
2. Hỗ trợ 2 chế độ:
   - Chưa đăng nhập (Guest): Hỏi trong notebook khách của mình, không giới hạn số câu hỏi (chỉ 1 tài liệu nguồn).
   - Đã đăng nhập (User): Có hạn mức câu hỏi mỗi ngày.
3. Lưu tin nhắn người dùng và phản hồi của trợ lý AI (kèm citations, token, độ trễ) vào MongoDB.
4. Lấy lịch sử hội thoại của một notebook (GET /api/v1/chat/messages/{notebook_id}).
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.shared.deps import can_chat, get_optional_user_id, require_notebook
from app.core.config import settings
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.chat.chat_repo import ChatRepository
from app.modules.documents.document import ACTIVE_STATUSES
from app.modules.documents.document_repo import DocumentRepository
from app.modules.auth.user_repo import UserRepository
from app.modules.chat.chat_models import MessageRecord
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator, SourceSelectionError

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


def selected_ids(document_ids: Optional[List[str]], document_id: Optional[str]) -> List[str]:
    """The sources chosen by the user: the list, or the single id of older clients."""
    return list(dict.fromkeys(document_ids or ([document_id] if document_id else [])))


async def ensure_documents_ready(db: AsyncIOMotorDatabase, notebook_id: str, document_ids: List[str]) -> None:
    """Strict chat gating: 409 while ANY document of the notebook is still being processed (a failed one does not block);
    422 if a selected document is unknown or failed."""
    docs = {d.document_id: d for d in await DocumentRepository(db).get_by_notebook(notebook_id)}
    if any(i not in docs for i in document_ids):
        raise HTTPException(status_code=422, detail="Có tài liệu được chọn không thuộc notebook này.")
    if any(d.status in ACTIVE_STATUSES for d in docs.values()):
        raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý và phân tích. Vui lòng đợi hệ thống báo sẵn sàng rồi đặt câu hỏi.")
    if any(docs[i].status == "failed" for i in document_ids):
        raise HTTPException(status_code=422, detail="Không xử lý được tài liệu này. Vui lòng thử tải lên lại hoặc chọn tệp PDF khác.")


# --- Schemas ---

class QueryRequest(BaseModel):
    notebook_id: str
    query: str
    document_id: Optional[str] = None  # one source (older clients)
    document_ids: Optional[List[str]] = None  # the sources selected by the user (at least one)
    mentions: Optional[List[str]] = None  # @file: selected documents the question is explicitly about (ids, never parsed from the text)


class QueryResponse(BaseModel):
    title: str  # the notebook's title: named after the first question
    query: str
    answer: str
    intent: str
    citations: List[dict]
    understood: str = ""  # G3: how the question was understood (documents, assumptions), shown above the answer
    alternatives: List[dict] = []  # other selected documents that also match: [{"document_id", "label"}]
    verification: dict = {}  # A2: {"passed", "repaired", "unverified_figures", "citations"}


# --- Endpoints ---

# ==============================================================================
# HÀM: handle_user_query
# Ý NGHĨA: Điểm đầu vào chính của quy trình hỏi đáp tài chính RAG:
#          1. Kiểm tra quyền truy cập notebook, nguồn tài liệu đã chọn và hạn mức.
#          2. Lưu tin nhắn của người dùng vào MongoDB collection `messages`.
#          3. Kích hoạt Orchestrator điều phối pipeline tìm kiếm ngữ nghĩa và sinh câu trả lời.
#          4. Ghi nhận hạn mức, lưu câu trả lời kèm trích dẫn và số liệu (token, độ trễ, model).
# ==============================================================================
@router.post("/query", response_model=QueryResponse)
async def handle_user_query(
    req: QueryRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Xử lý câu hỏi tài chính, thực thi luồng RAG và lưu lịch sử vào MongoDB."""
    # 0. Tài liệu phải xử lý xong mới truy vấn được; chặn trước khi trừ hạn mức
    nb = await require_notebook(db, req.notebook_id, user_id)
    if not can_chat(nb, user_id):
        raise HTTPException(status_code=403, detail="Hãy đăng nhập để đặt câu hỏi trên notebook này.")
    chosen = selected_ids(req.document_ids, req.document_id)
    limit = settings.MAX_SELECTED_DOCS_USER if user_id else settings.MAX_SELECTED_DOCS_GUEST
    if not chosen:
        raise HTTPException(status_code=422, detail="Hãy chọn tài liệu nguồn trước khi đặt câu hỏi.")
    if len(chosen) > limit:
        raise HTTPException(status_code=422, detail=f"Chỉ được chọn tối đa {limit} tài liệu nguồn cho một câu hỏi.")
    mentions = list(dict.fromkeys(req.mentions or []))
    if any(m not in chosen for m in mentions):
        raise HTTPException(status_code=422, detail="Chỉ tag (@) được các tài liệu nguồn đã chọn.")
    await ensure_documents_ready(db, req.notebook_id, chosen)
    users = UserRepository(db)
    if user_id is not None and not await users.check_quota(user_id):
        raise HTTPException(status_code=429, detail="Bạn đã dùng hết số câu hỏi của hôm nay. Vui lòng quay lại vào ngày mai.")
    orchestrator = RAGWorkflowOrchestrator(db, qdrant)
    try:  # a question without a usable source choice is refused before it costs quota or writes a message
        await orchestrator.resolve_scope(req.notebook_id, chosen)
    except SourceSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    chat_repo = ChatRepository(db)

    # 1. Các lượt trước (để hiểu câu hỏi nối tiếp như "còn lợi nhuận thì sao?")
    history = [
        {"role": m.role, "content": m.content, "citations": [c.model_dump() for c in m.citations]}
        for m in await chat_repo.get_messages(req.notebook_id, limit=6)
    ]

    # 2. Kích hoạt RAG Workflow Orchestrator
    result = await orchestrator.execute_query(
        query=req.query,
        notebook_id=req.notebook_id,
        document_ids=chosen,
        history=history,
        mentions=mentions,
    )

    # 3. Câu hỏi chỉ được lưu khi đã có câu trả lời: câu hỏi lỗi không kẹt lại trong lịch sử và ngữ cảnh. Câu đầu tiên đặt tên cho đoạn chat
    title = nb.title
    if nb.message_count == 0:
        title = req.query[:40]
        await chat_repo.set_title(req.notebook_id, title)
    await chat_repo.append_message(
        MessageRecord(message_id=f"msg_{uuid.uuid4().hex[:8]}", notebook_id=req.notebook_id, role="user", content=req.query)
    )

    # Người dùng đã đăng nhập: chỉ tính lượt hỏi khi hệ thống đã thật sự tìm và sinh câu trả lời
    # (từ chối, câu chào, lệnh liệt kê nguồn, hỏi lại... không bị tính); token thì luôn ghi đúng lượng đã dùng
    trace = result.get("trace", {})
    llm = trace.get("llm", {})
    prompt_tokens, completion_tokens = llm.get("prompt_tokens", 0), llm.get("completion_tokens", 0)
    if user_id is not None:
        await users.consume_quota(user_id, messages=1 if result.get("charged", True) else 0, tokens=prompt_tokens + completion_tokens)

    # 4. Lưu câu trả lời của AI kèm trích dẫn và số liệu thực nghiệm vào MongoDB
    await chat_repo.append_message(
        MessageRecord(
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            notebook_id=req.notebook_id,
            role="assistant",
            content=result["answer"],
            citations=result["citations"],
            trace_info={"intent": result["intent"], **trace},
            token_usage={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens},
            latency_ms=round(trace.get("timings", {}).get("total", 0) * 1000),
            model_used=settings.DEFAULT_LLM_MODEL if llm.get("calls") else None,
        )
    )

    return QueryResponse(
        title=title,
        query=req.query,
        answer=result["answer"],
        intent=result["intent"],
        citations=result["citations"],
        understood=result.get("understood", ""),
        alternatives=result.get("alternatives", []),
        verification=result.get("verification", {}),
    )


# ==============================================================================
# HÀM: get_messages
# Ý NGHĨA: Lấy lịch sử tin nhắn của một notebook để Frontend hiển thị lại đoạn chat.
# ==============================================================================
@router.get("/messages/{notebook_id}", response_model=List[MessageRecord])
async def get_messages(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy các tin nhắn mới nhất của một notebook, theo đúng thứ tự hội thoại."""
    await require_notebook(db, notebook_id, user_id)
    return await ChatRepository(db).get_messages(notebook_id)
