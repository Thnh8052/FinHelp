"""
API Router: Quản Lý & Tải Lên Tài Liệu (Document Upload & Ingestion)
Tác giả: Vũ Thành - FinAnalyst AI

Chịu trách nhiệm:
1. Tiếp nhận tệp PDF báo cáo tài chính tải lên (POST /api/v1/documents/upload/{notebook_id}).
2. Hỗ trợ 2 chế độ hạn mức:
   - Chưa đăng nhập (Guest): Giới hạn tối đa 1 tài liệu.
   - Đã đăng nhập (User): Giới hạn tối đa 5 tài liệu mỗi Notebook.
3. Lưu trữ tệp vào hệ thống Local Storage và lập bản ghi DocumentRecord trong MongoDB.
4. Kích hoạt Ingestion Pipeline chạy ngầm (BackgroundTasks): trích xuất văn bản, bảng biểu, vector embedding vào Qdrant.
5. Truy vấn danh sách tài liệu trong sổ tay (GET /api/v1/documents/notebook/{notebook_id}).
6. Theo dõi trạng thái tiến độ xử lý tài liệu (GET /api/v1/documents/jobs/{job_id}).
"""

import asyncio
import hashlib
from pathlib import Path
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError
from qdrant_client import AsyncQdrantClient

from app.shared.deps import get_optional_user_id, require_notebook
from app.core.config import settings
from app.core.logging import logger
from app.infrastructure.database.mongodb import get_database
from app.infrastructure.database.qdrant import get_qdrant_client
from app.modules.ingestion.chunk_repo import ChunkRepository
from app.modules.documents.document_repo import DocumentRepository
from app.modules.ingestion.ingestion_job_repo import IngestionJobRepository
from app.modules.auth.user import tier_spec
from app.modules.auth.user_repo import UserRepository
from app.modules.documents.document import ACTIVE_STATUSES, DocumentRecord
from app.modules.ingestion.ingestion_job import IngestionJobRecord
from app.modules.documents.catalog_edit import REPORT_TYPES, CatalogUpdate, catalog_changes, needs_confirmation
from app.modules.ingestion.pipeline import IngestionPipeline
from app.infrastructure.storage.local_fs import StorageService
from app.modules.notebooks.notebook_repo import NotebookRepository
from app.modules.notebooks.purge import purge_document

router = APIRouter(prefix="/documents", tags=["Documents & Ingestion"])


# ==============================================================================
# HÀM: list_documents
# Ý NGHĨA: Lấy danh sách các tài liệu PDF đã nạp vào một sổ tay (notebook_id).
#          Hỗ trợ cả người dùng đăng nhập lẫn khách dùng thử chưa đăng nhập.
# ĐẦU VÀO:
#   - notebook_id: Mã định danh sổ tay.
#   - user_id: Lấy tùy chọn từ JWT (None nếu là Guest).
# ĐẦU RA:
#   - List[DocumentRecord]: Danh sách tài liệu trong sổ tay.
# ==============================================================================
@router.get("/notebook/{notebook_id}", response_model=List[DocumentRecord])
async def list_documents(
    notebook_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Lấy danh sách các tài liệu thuộc về Notebook chỉ định."""
    await require_notebook(db, notebook_id, user_id)
    repo = DocumentRepository(db)
    return await repo.get_by_notebook(notebook_id)


def _compute_sha256(file_path: Path) -> str:
    """Tính mã băm SHA-256 của nội dung tệp tin để chống trùng lặp dữ liệu."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


async def _check_upload(db: AsyncIOMotorDatabase, file: UploadFile, user_id: Optional[str]) -> None:
    """Refuse a file before it reaches storage: larger than the caller's limit, or not a PDF whatever its name says."""
    role = None
    if user_id is not None:
        user = await UserRepository(db).get_by_id(user_id)
        role = user.role if user else "user"
    limit_mb = tier_spec(role)["max_file_size_mb"]
    if (file.size or 0) > limit_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Dung lượng tệp vượt quá giới hạn {limit_mb} MB của tài khoản.")
    head = await file.read(1024)
    await file.seek(0)
    if b"%PDF-" not in head:
        raise HTTPException(status_code=400, detail="Tệp này không phải là PDF hợp lệ.")


# ==============================================================================
# HÀM: upload_pdf
# Ý NGHĨA: Tiếp nhận tệp PDF BCTC, kiểm tra hạn mức (Guest: tối đa 1 doc; User: tối đa 5 docs),
#          lưu trữ file và khởi chạy Ingestion Pipeline ngầm.
# ĐẦU VÀO:
#   - notebook_id: Mã sổ tay chứa tài liệu.
#   - file: Tệp PDF người dùng gửi lên.
#   - user_id: None nếu chưa đăng nhập (Guest), chuỗi user_id nếu đã đăng nhập.
# ĐẦU RA:
#   - JSON thông báo trạng thái, document_id và job_id để frontend theo dõi.
# ==============================================================================
@router.post("/upload/{notebook_id}")
async def upload_pdf(
    notebook_id: str,
    file: UploadFile = File(...),
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Tải lên tệp PDF Báo cáo tài chính và khởi chạy tiến trình trích xuất."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hệ thống hiện tại chỉ hỗ trợ định dạng tệp PDF.")

    await require_notebook(db, notebook_id, user_id, write=True)
    await _check_upload(db, file, user_id)
    doc_repo = DocumentRepository(db)
    # Failed documents do not count toward the quota: otherwise one failed upload would block every retry.
    existing_docs = [d for d in await doc_repo.get_by_notebook(notebook_id) if d.status != "failed"]

    # 0. Kiểm tra trùng lặp tên tệp trong sổ tay (Deduplication Check)
    clean_filename = file.filename.strip()
    for d in existing_docs:
        if d.file_name.strip().lower() == clean_filename.lower():
            if d.status in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=409,
                    detail=f"Tài liệu '{clean_filename}' đang được xử lý trong sổ tay. Vui lòng không tải lại.",
                )
            raise HTTPException(
                status_code=409,
                detail=f"Tài liệu '{clean_filename}' đã tồn tại trong sổ tay. Vui lòng xóa tài liệu cũ nếu muốn tải lên lại.",
            )

    # 1. Kiểm tra hạn mức tài liệu (Quota Gate)
    if user_id is None:
        # Khách chưa đăng nhập: Tối đa 1 tài liệu
        if len(existing_docs) >= settings.MAX_SELECTED_DOCS_GUEST:
            raise HTTPException(
                status_code=403,
                detail="Chế độ dùng thử (chưa đăng nhập) chỉ hỗ trợ tối đa 1 tài liệu. Vui lòng đăng nhập để phân tích tối đa 5 tài liệu!",
            )
    else:
        # Người dùng đã đăng nhập: Tối đa 5 tài liệu / notebook
        if len(existing_docs) >= settings.MAX_SELECTED_DOCS_USER:
            raise HTTPException(
                status_code=403,
                detail="Bạn đã đạt giới hạn tối đa 5 tài liệu trong sổ tay này. Vui lòng tạo sổ tay mới hoặc xóa tài liệu cũ.",
            )

    storage = StorageService()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    job_id = f"job_{uuid.uuid4().hex[:8]}"

    # 2. Lưu file vật lý vào thư mục lưu trữ
    saved_path = await storage.save_pdf(notebook_id, doc_id, file)
    file_hash = await asyncio.to_thread(_compute_sha256, saved_path)

    # 2.1. Kiểm tra trùng lặp nội dung tệp bằng mã băm SHA-256 (Content Hash Deduplication)
    for d in existing_docs:
        if d.file_hash and d.file_hash == file_hash:
            # Xóa file tạm vừa ghi vì nội dung đã tồn tại
            try:
                saved_path.unlink(missing_ok=True)
            except Exception:
                pass

            if d.status in ACTIVE_STATUSES:
                raise HTTPException(
                    status_code=409,
                    detail=f"Tệp này có nội dung trùng với '{d.file_name}' đang được xử lý trong sổ tay.",
                )
            raise HTTPException(
                status_code=409,
                detail=f"Tệp này có nội dung trùng hoàn toàn với tài liệu '{d.file_name}' đã có trong sổ tay.",
            )

    # 3. Tạo bản ghi DocumentRecord trong MongoDB
    doc_record = DocumentRecord(
        document_id=doc_id,
        notebook_id=notebook_id,
        file_name=file.filename,
        file_size_bytes=saved_path.stat().st_size,
        file_path=saved_path.relative_to(settings.STORAGE_LOCAL_DIR).as_posix(),
        file_hash=file_hash,
    )
    try:
        await doc_repo.save_document(doc_record)
    except DuplicateKeyError:  # two uploads of the same content raced past the check above
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Tệp này có nội dung trùng với một tài liệu đã có trong sổ tay.")

    # 4. Tạo bản ghi IngestionJobRecord theo dõi tiến độ
    job_repo = IngestionJobRepository(db)
    job_record = IngestionJobRecord(
        job_id=job_id,
        document_id=doc_id,
        notebook_id=notebook_id,
    )
    await job_repo.save_job(job_record)
    await NotebookRepository(db).touch(notebook_id)

    # 5. Xếp vào hàng đợi xử lý: chạy độc lập với trình duyệt, người dùng F5 hay mất mạng vẫn xử lý tiếp
    await IngestionPipeline(db, qdrant).run(job_id, doc_id, notebook_id, saved_path)

    return {
        "message": "Tải tệp lên thành công. Hệ thống đang tiến hành trích xuất dữ liệu.",
        "document_id": doc_id,
        "job_id": job_id,
    }


# ==============================================================================
# HÀM: get_job_status
# Ý NGHĨA: Truy vấn trạng thái và tiến độ phần trăm (% progress) của tiến trình trích xuất tài liệu.
# ĐẦU VÀO:
#   - job_id: Mã tiến trình.
# ĐẦU RA:
#   - IngestionJobRecord: Trạng thái hiện tại (parsing, extracting_tables, indexing, completed).
# ==============================================================================
@router.get("/jobs/{job_id}", response_model=IngestionJobRecord)
async def get_job_status(
    job_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Truy vấn tiến độ xử lý trích xuất tài liệu theo Job ID."""
    job_repo = IngestionJobRepository(db)
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Không tìm thấy tiến trình xử lý")
    await require_notebook(db, job.notebook_id, user_id)
    return job


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Permanently remove one source and every derived artifact it owns."""
    document = await _document(db, document_id, user_id, write=True)
    if document.status in ACTIVE_STATUSES:  # so a running ingestion can never recreate data after this cleanup
        raise HTTPException(status_code=409, detail="Tài liệu đang được xử lý. Vui lòng đợi xử lý xong rồi mới xóa.")
    try:
        await purge_document(db, qdrant, document)
    except Exception as exc:  # the record is removed last, so a retry stays possible
        logger.error(f"Could not purge document {document_id}: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=503, detail="Không thể xóa đầy đủ dữ liệu của tài liệu. Vui lòng thử lại.") from exc

    return {"message": "Đã xóa tài liệu và dữ liệu phân tích liên quan.", "document_id": document_id}


# ==============================================================================
# HÀM: get_catalog / update_catalog
# Ý NGHĨA: Mẫu xác nhận danh tính tài liệu (công ty, mã CK, tên khác, loại báo cáo, kỳ). Tên công ty nên chọn từ các tên tìm
#          được trong tài liệu (name_candidates, kèm trang); giá trị gõ tay không có trong tài liệu được lưu nhưng gắn cờ.
#          Chỉ chủ notebook (hoặc khách trong notebook khách của mình) được sửa; notebook mẫu chỉ đọc.
# ==============================================================================
async def _document(db: AsyncIOMotorDatabase, document_id: str, user_id: Optional[str], write: bool = False) -> DocumentRecord:
    doc = await DocumentRepository(db).get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
    await require_notebook(db, doc.notebook_id, user_id, write=write)
    return doc


CATALOG_FIELDS = {"company_name", "ticker", "aliases", "report_type", "fiscal_year", "fiscal_quarter", "period_end", "period_start",
                  "years_covered", "catalog_source", "catalog_unverified", "catalog_confirmed", "user_override_unverified", "name_candidates"}


@router.get("/{document_id}/catalog")
async def get_catalog(
    document_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await _document(db, document_id, user_id)
    return {"document_id": doc.document_id, "file_name": doc.file_name, "needs_confirmation": needs_confirmation(doc),
            "metadata": doc.metadata.model_dump(include=CATALOG_FIELDS), "report_types": REPORT_TYPES}


@router.patch("/{document_id}/catalog")
async def update_catalog(
    document_id: str,
    req: CatalogUpdate,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    doc = await _document(db, document_id, user_id, write=True)
    text = " ".join(c.content for c in await ChunkRepository(db).get_chunks_by_document(document_id))
    changes = catalog_changes(doc, req, text, user_id or "guest")
    await DocumentRepository(db).update_one({"document_id": document_id}, changes)
    return {"document_id": document_id, "needs_confirmation": False, "user_override_unverified": changes["metadata.user_override_unverified"]}


# ==============================================================================
# HÀM: get_document_file
# Ý NGHĨA: Phục vụ tệp PDF gốc để trình đọc BCTC Split-View tải trực tiếp.
# ==============================================================================
@router.get("/{document_id}/file/{token}")
@router.get("/{document_id}/file")
async def get_document_file(
    document_id: str,
    token: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    from fastapi.responses import FileResponse
    from jose import JWTError, jwt

    # Thẻ <iframe> trong trình duyệt không gửi header Authorization: Bearer, do đó nhận token qua Query Param
    if not user_id and token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
        except JWTError:
            pass

    doc = await _document(db, document_id, user_id, write=False)
    storage = StorageService()
    pdf_path = storage.get_pdf_path(doc.notebook_id, doc.document_id, doc.file_name)
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Tệp PDF không tồn tại trên hệ thống lưu trữ.")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=doc.file_name,  # encoded by Starlette: a raw header fails on Vietnamese names such as "tổng hợp"
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},  # a document's PDF never changes: reuse it instead of downloading it again
    )
