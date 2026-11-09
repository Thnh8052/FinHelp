"""MongoDB Collection Names.

Corresponds to the 6 primary collections of the architecture:
- users: Tài khoản và hạn mức của người dùng đã đăng ký
- notebooks: Không gian phân tích, mỗi notebook là một đoạn chat
- documents: Hồ sơ PDF, trạng thái xử lý và danh mục BCTC
- chunks: Nội dung chunk chuẩn, vị trí trang, thông tin nguồn
- messages: Câu hỏi, câu trả lời, citations và thông tin trace
- ingestion_jobs: Trạng thái job, bước đang chạy, lỗi và thời gian xử lý
"""

USERS_COLLECTION = "users"
NOTEBOOKS_COLLECTION = "notebooks"
DOCUMENTS_COLLECTION = "documents"
CHUNKS_COLLECTION = "chunks"
MESSAGES_COLLECTION = "messages"
INGESTION_JOBS_COLLECTION = "ingestion_jobs"
