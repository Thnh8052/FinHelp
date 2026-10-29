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

import uuid
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.api.v1.deps import get_optional_user_id, require_notebook
from app.core.config import settings
from app.db.mongodb import get_database
from app.db.qdrant import get_qdrant_client
from app.db.repositories.chunk_repo import ChunkRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.ingestion_job_repo import IngestionJobRepository
from app.models.document import DocumentRecord
from app.models.ingestion_job import IngestionJobRecord
from app.services.ingestion.catalog_edit import REPORT_TYPES, CatalogUpdate, catalog_changes, needs_confirmation
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.storage.local_fs import StorageService

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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
):
    """Tải lên tệp PDF Báo cáo tài chính và khởi chạy tiến trình trích xuất."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hệ thống hiện tại chỉ hỗ trợ định dạng tệp PDF.")

    await require_notebook(db, notebook_id, user_id, write=True)
    doc_repo = DocumentRepository(db)
    # Failed documents do not count toward the quota: otherwise one failed upload would block every retry.
    existing_docs = [d for d in await doc_repo.get_by_notebook(notebook_id) if d.parsing_status != "failed"]

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

    # 3. Tạo bản ghi DocumentRecord trong MongoDB
    doc_record = DocumentRecord(
        document_id=doc_id,
        notebook_id=notebook_id,
        file_name=file.filename,
        file_size_bytes=saved_path.stat().st_size,
        file_path=str(saved_path),
        parsing_status="processing",
        indexing_status="pending",
    )
    await doc_repo.save_document(doc_record)

    # 4. Tạo bản ghi IngestionJobRecord theo dõi tiến độ
    job_repo = IngestionJobRepository(db)
    job_record = IngestionJobRecord(
        job_id=job_id,
        document_id=doc_id,
        notebook_id=notebook_id,
        status="parsing",
        progress_percent=10,
    )
    await job_repo.save_job(job_record)

    # 5. Kích hoạt Ingestion Pipeline chạy nền
    pipeline = IngestionPipeline(db, qdrant)
    background_tasks.add_task(pipeline.run, job_id, doc_id, notebook_id, saved_path)

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
    doc_repo = DocumentRepository(db)
    # This marker makes any queued/running ingestion stop before it can write a
    # chunk or vector after this endpoint has cleaned it up.
    await doc_repo.update_one(
        {"document_id": document_id},
        {"parsing_status": "deleting", "indexing_status": "deleting"},
    )

    try:
        if await qdrant.collection_exists(settings.QDRANT_COLLECTION_NAME):
            await qdrant.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(must=[models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=document_id)
                    )])
                ),
                wait=True,
            )
    except Exception as exc:
        # Do not remove the source record if its search index could not be cleaned:
        # a retry must remain possible and must not leave a hidden searchable document.
        await doc_repo.update_one(
            {"document_id": document_id},
            {"parsing_status": document.parsing_status, "indexing_status": document.indexing_status},
        )
        raise HTTPException(status_code=503, detail="Không thể dọn dữ liệu tìm kiếm của tài liệu. Vui lòng thử lại.") from exc

    storage = StorageService()
    try:
        await storage.delete_document_files(document.notebook_id, document.document_id, document.file_path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Không thể xóa tệp tài liệu trên máy chủ. Vui lòng thử lại.") from exc

    await ChunkRepository(db).delete_by_document(document_id)
    await IngestionJobRepository(db).delete_by_document(document_id)
    await doc_repo.delete_document(document_id)

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
