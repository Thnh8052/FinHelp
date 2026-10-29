"""
API Router: Phiên Chat & Truy Vấn RAG Tài Chính (Chat Sessions & Financial RAG)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Tiếp nhận câu hỏi tài chính từ người dùng (POST /api/v1/chat/query).
2. Hỗ trợ 2 chế độ:
   - Chưa đăng nhập (Guest): Hỏi trong notebook khách của mình, không giới hạn số câu hỏi (chỉ 1 tài liệu nguồn).
   - Đã đăng nhập (User): Được lưu vết đầy đủ trong hồ sơ tài khoản.
3. Tự động khởi tạo phiên hội thoại (Chat Session) nếu chưa có session_id.
4. Lưu vết tin nhắn người dùng và phản hồi của trợ lý AI (kèm citations) vào MongoDB.
5. Lấy lịch sử hội thoại của một phiên (GET /api/v1/chat/sessions/{session_id}/messages).
6. Quản lý danh sách các phiên chat trong sổ tay (GET /api/v1/chat/sessions/notebook/{notebook_id}).
7. Tạo mới và Xóa phiên chat kèm dọn dẹp tin nhắn (POST /sessions & DELETE /sessions/{session_id}).
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.api.v1.deps import can_chat, get_optional_user_id, owns_session, require_notebook, session_owner
from app.core.config import settings
from app.db.mongodb import get_database
from app.db.qdrant import get_qdrant_client
from app.db.repositories.chat_repo import ChatRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.user_repo import UserRepository
from app.models.chat import ChatSessionRecord, MessageRecord
from app.services.rag_workflow.orchestrator import RAGWorkflowOrchestrator, SourceSelectionError

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


def selected_ids(document_ids: Optional[List[str]], document_id: Optional[str]) -> List[str]:
    """The sources chosen by the user: the list, or the single id of older clients."""
    return list(dict.fromkeys(document_ids or ([document_id] if document_id else [])))


async def ensure_documents_ready(db: AsyncIOMotorDatabase, notebook_id: str, document_ids: List[str]) -> None:
    """With a selection: 422 if a selected document is unknown / failed, 409 while one is still processing.
    Without: 409 while every document of the notebook is still being processed, 422 if all failed."""
    repo = DocumentRepository(db)
    if document_ids:
        docs = [await repo.get_by_id(i) for i in document_ids]
        if any(d is None or d.notebook_id != notebook_id for d in docs):
            raise HTTPException(status_code=422, detail="Có tài liệu được chọn không thuộc notebook này.")
        if any(d.parsing_status == "failed" for d in docs):
            raise HTTPException(status_code=422, detail="Không xử lý được tài liệu này. Vui lòng thử tải lên lại hoặc chọn tệp PDF khác.")
        if any(d.indexing_status != "completed" for d in docs):
            raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý và phân tích. Vui lòng đợi hệ thống báo sẵn sàng rồi đặt câu hỏi.")
        return
    docs = await repo.get_by_notebook(notebook_id)
    if not docs or any(d.indexing_status == "completed" for d in docs):
        return  # nothing uploaded yet is answered by the orchestrator; any ready document is enough
    if all(d.parsing_status == "failed" for d in docs):
        raise HTTPException(status_code=422, detail="Không xử lý được tài liệu này. Vui lòng thử tải lên lại hoặc chọn tệp PDF khác.")
    raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý và phân tích. Vui lòng đợi hệ thống báo sẵn sàng rồi đặt câu hỏi.")


# --- Schemas ---

class QueryRequest(BaseModel):
    notebook_id: str
    session_id: Optional[str] = None
    query: str
    document_id: Optional[str] = None  # one source (older clients)
    document_ids: Optional[List[str]] = None  # the sources selected by the user (at least one)
    mentions: Optional[List[str]] = None  # @file: selected documents the question is explicitly about (ids, never parsed from the text)


class QueryResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    intent: str
    citations: List[dict]
    understood: str = ""  # G3: how the question was understood (documents, assumptions), shown above the answer
    alternatives: List[dict] = []  # other selected documents that also match: [{"document_id", "label"}]
    verification: dict = {}  # A2: {"passed", "repaired", "unverified_figures", "citations"}


class CreateSessionRequest(BaseModel):
    notebook_id: str
    title: Optional[str] = "Hội thoại mới"


# --- Endpoints ---

# ==============================================================================
# HÀM: handle_user_query
# Ý NGHĨA: Điểm đầu vào chính của quy trình hỏi đáp tài chính RAG (Retrieval-Augmented Generation):
#          1. Kiểm tra quyền truy cập notebook, phiên chat và nguồn tài liệu đã chọn.
#          2. Tự tạo phiên chat mới trong MongoDB nếu chưa có session_id.
#          3. Lưu tin nhắn của người dùng vào MongoDB collection `messages`.
#          4. Kích hoạt Orchestrator điều phối pipeline tìm kiếm ngữ nghĩa và sinh câu trả lời.
#          5. Lưu câu trả lời của AI kèm danh sách trích dẫn (citations).
#          6. Cập nhật số lượt hỏi vào MongoDB và trả về kết quả cho Frontend.
# ĐẦU VÀO:
#   - req (QueryRequest): notebook_id, session_id, query (câu hỏi), document_id.
#   - user_id: Mã người dùng nếu đã đăng nhập, hoặc None nếu là Guest.
#   - db: Kết nối MongoDB Motor.
#   - qdrant: Kết nối cơ sở dữ liệu vector Qdrant.
# ĐẦU RA:
#   - QueryResponse: session_id, query, answer, intent, citations.
# ==============================================================================
@router.post("/query", response_model=QueryResponse)
async def handle_user_query(
    req: QueryRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Xử lý câu hỏi tài chính, thực thi luồng RAG và lưu lịch sử vào MongoDB."""
    # 0. Tài liệu phải xử lý xong mới truy vấn được (nạp Docling có thể mất vài phút); chặn trước khi trừ hạn mức
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
    orchestrator = RAGWorkflowOrchestrator(db, qdrant)
    try:  # a question without a usable source choice is refused before it costs quota or creates a session
        await orchestrator.resolve_scope(req.notebook_id, chosen)
    except SourceSelectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    chat_repo = ChatRepository(db)

    # 1. Quản lý phiên hội thoại
    # A session id sent by the client must be the caller's own, in this notebook: its history is fed to the model.
    session_id = req.session_id
    if session_id:
        session = await chat_repo.get_session(session_id)
        if not session or session.notebook_id != req.notebook_id or not owns_session(session, user_id):
            raise HTTPException(status_code=403, detail="Không có quyền dùng phiên hội thoại này")
    else:
        session_id = f"ses_{uuid.uuid4().hex}"
        session = ChatSessionRecord(
            session_id=session_id,
            notebook_id=req.notebook_id,
            user_id=session_owner(user_id),
            title=req.query[:40],
        )
        await chat_repo.save_session(session)

    # Các lượt trước của phiên (để hiểu câu hỏi nối tiếp như "còn lợi nhuận thì sao?")
    existing_msgs = await chat_repo.get_messages(session_id, limit=200)
    history = [{"role": m.role, "content": m.content, "citations": [c.model_dump() for c in m.citations]} for m in existing_msgs[-6:]]

    # 2. Lưu tin nhắn người dùng vào MongoDB
    user_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    await chat_repo.append_message(
        MessageRecord(
            message_id=user_msg_id,
            session_id=session_id,
            role="user",
            content=req.query,
        )
    )

    # 3. Kích hoạt RAG Workflow Orchestrator
    result = await orchestrator.execute_query(
        query=req.query,
        notebook_id=req.notebook_id,
        document_ids=chosen,
        history=history,
        mentions=mentions,
    )

    # Người dùng đã đăng nhập: ghi nhận số lượt hỏi; chỉ tính khi hệ thống đã thật sự tìm và sinh câu trả lời
    # (từ chối, câu chào, lệnh liệt kê nguồn, hỏi lại... không bị tính)
    if user_id is not None and result.get("charged", True):
        await UserRepository(db).increment_quota_usage(user_id, messages=1)

    # 4. Lưu câu trả lời của AI kèm trích dẫn và tính toán tài chính vào MongoDB
    asst_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
    await chat_repo.append_message(
        MessageRecord(
            message_id=asst_msg_id,
            session_id=session_id,
            role="assistant",
            content=result["answer"],
            citations=result["citations"],
            trace_info={
                "intent": result["intent"],
                **result.get("trace", {}),
            },
        )
    )

    return QueryResponse(
        session_id=session_id,
        query=req.query,
        answer=result["answer"],
        intent=result["intent"],
        citations=result["citations"],
        understood=result.get("understood", ""),
        alternatives=result.get("alternatives", []),
        verification=result.get("verification", {}),
    )


# ==============================================================================
# HÀM: get_session_messages
# Ý NGHĨA: Lấy toàn bộ lịch sử tin nhắn của một phiên hội thoại cụ thể từ collection `messages`
#          để Frontend hiển thị lại dòng trao đổi khi người dùng bấm vào một phiên chat cũ.
# ĐẦU VÀO:
#   - session_id: Mã phiên hội thoại.
#   - user_id: Lấy tùy chọn từ JWT (None nếu là Guest).
# ĐẦU RA:
#   - List[MessageRecord]: Danh sách tin nhắn sắp xếp theo thứ tự thời gian.
# ==============================================================================
@router.get("/sessions/{session_id}/messages", response_model=List[MessageRecord])
async def get_session_messages(
    session_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy toàn bộ lịch sử tin nhắn của một phiên hội thoại từ MongoDB."""
    chat_repo = ChatRepository(db)
    session = await chat_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại")
    await require_notebook(db, session.notebook_id, user_id)
    if not owns_session(session, user_id):
        raise HTTPException(status_code=403, detail="Không có quyền xem phiên hội thoại này")
    return await chat_repo.get_messages(session_id)


# ==============================================================================
# HÀM: list_notebook_sessions
# Ý NGHĨA: Lấy danh sách các phiên hội thoại thuộc một sổ tay (notebook_id) cụ thể.
# ĐẦU VÀO:
#   - notebook_id: Mã sổ tay.
#   - user_id: Lấy tùy chọn từ JWT.
# ĐẦU RA:
#   - List[ChatSessionRecord]: Danh sách các phiên hội thoại trong sổ tay.
# ==============================================================================
@router.get("/sessions/notebook/{notebook_id}", response_model=List[ChatSessionRecord])
async def list_notebook_sessions(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy danh sách các phiên hội thoại trong Notebook."""
    nb = await require_notebook(db, notebook_id, user_id)
    chat_repo = ChatRepository(db)
    sessions = [s for s in await chat_repo.get_sessions_by_notebook(notebook_id) if owns_session(s, user_id)]
    if not sessions and user_id and can_chat(nb, user_id):
        default_ses = ChatSessionRecord(
            session_id=f"ses_{uuid.uuid4().hex}",
            notebook_id=notebook_id,
            user_id=user_id,
            title="Đoạn chat phân tích",
        )
        await chat_repo.save_session(default_ses)
        return [default_ses]
    return sessions


# ==============================================================================
# HÀM: create_chat_session
# Ý NGHĨA: Chủ động tạo một phiên hội thoại mới trong Sổ tay theo yêu cầu người dùng.
# ĐẦU VÀO:
#   - req (CreateSessionRequest): notebook_id, title (tiêu đề phiên chat).
#   - user_id: Mã người dùng (hoặc 'guest' nếu chưa đăng nhập).
# ĐẦU RA:
#   - ChatSessionRecord: Phiên hội thoại vừa được tạo.
# ==============================================================================
@router.post("/sessions", response_model=ChatSessionRecord)
async def create_chat_session(
    req: CreateSessionRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Tạo một phiên hội thoại mới trong Notebook (yêu cầu đăng nhập)."""
    if not user_id:
        raise HTTPException(
            status_code=403,
            detail="Bạn cần đăng nhập để tạo thêm đoạn chat mới và lưu trữ lịch sử!",
        )

    nb = await require_notebook(db, req.notebook_id, user_id)
    if not can_chat(nb, user_id):
        raise HTTPException(status_code=403, detail="Không có quyền tạo phiên hội thoại trong notebook này")
    chat_repo = ChatRepository(db)
    session_id = f"ses_{uuid.uuid4().hex}"
    session = ChatSessionRecord(
        session_id=session_id,
        notebook_id=req.notebook_id,
        user_id=user_id,
        title=req.title or "Hội thoại mới",
    )
    await chat_repo.save_session(session)
    return session


# ==============================================================================
# HÀM: delete_chat_session
# Ý NGHĨA: Xóa một phiên hội thoại khỏi MongoDB và kích hoạt xóa toàn bộ tin nhắn liên quan
#          (Cascade Delete) để giải phóng dung lượng và bảo mật dữ liệu.
# ĐẦU VÀO:
#   - session_id: Mã phiên chat cần xóa.
#   - user_id: Người dùng đăng nhập (phải là chủ sở hữu phiên chat).
# ĐẦU RA:
#   - JSON thông báo xóa phiên hội thoại thành công.
# ==============================================================================
@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Xóa một phiên hội thoại và dọn dẹp tin nhắn khỏi MongoDB."""
    chat_repo = ChatRepository(db)
    session = await chat_repo.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên hội thoại")
    await require_notebook(db, session.notebook_id, user_id)
    if not owns_session(session, user_id):  # a guest (user_id None) must not delete a signed-in user's chat
        raise HTTPException(status_code=403, detail="Không có quyền xóa phiên hội thoại này")
    success = await chat_repo.delete_session(session_id)
    return {"success": success, "message": "Đã xóa phiên hội thoại thành công"}
