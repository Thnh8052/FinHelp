"""MongoDB Collection Names.

Corresponds to the 7 primary collections identified in the architecture:
- users: Tài khoản và thông tin người dùng
- notebooks: Notebook và cấu hình notebook
- documents: PDF metadata, trạng thái parsing và indexing
- chunks: Nội dung chunk chuẩn, vị trí trang, thông tin nguồn
- chat_sessions: Phiên hội thoại, notebook đang sử dụng
- messages: Câu hỏi, câu trả lời, citations và thông tin trace
- ingestion_jobs: Trạng thái job, lỗi, retry và tiến trình xử lý
"""

USERS_COLLECTION = "users"
NOTEBOOKS_COLLECTION = "notebooks"
DOCUMENTS_COLLECTION = "documents"
CHUNKS_COLLECTION = "chunks"
CHAT_SESSIONS_COLLECTION = "chat_sessions"
MESSAGES_COLLECTION = "messages"
INGESTION_JOBS_COLLECTION = "ingestion_jobs"
