"""Replies that need no retrieval and no generation (not charged to the user's quota), and the fixed answer texts."""
from typing import Any, Dict, List, Optional

from app.modules.documents.document import DocumentRecord
from app.modules.chat.scope import document_label

# Appended by code to an answer that found nothing (docs/Version_2/fail_cases.md, S2): never suggests a document outside the selected sources
CHECK_SOURCES = {"vi": "Hãy kiểm tra lại các nguồn đã chọn hoặc tài liệu đã tải lên.",
                 "en": "Please check the selected sources or the uploaded documents."}
# Appended to the answer of a "search again" click that still found nothing, or not enough (S3/S5): there is no further button
RETRY_APOLOGY = {"vi": "Xin lỗi, trong giới hạn hiện tại hệ thống chưa tìm được đủ thông tin này. " + CHECK_SOURCES["vi"],
                 "en": "Sorry, within its current limits the system could not find enough of this information. " + CHECK_SOURCES["en"]}
NO_DATA_ANSWER = {"vi": "Không tìm thấy dữ liệu tài chính phù hợp trong tài liệu của notebook này. " + CHECK_SOURCES["vi"],
                  "en": "No matching financial data was found in this notebook's documents. " + CHECK_SOURCES["en"]}


def terminal(action: str, message: str, trace: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A reply that needs no retrieval and no generation: not charged to the user's quota."""
    return {"answer": message, "intent": action, "citations": [], "retrieved_chunks_count": 0, "charged": False, "trace": trace or {}}


def sources_message(scope: List[DocumentRecord], lang: str) -> str:
    lines = [f"{n}. {document_label(d)}" + (f" — {d.page_count} {'trang' if lang == 'vi' else 'pages'}" if d.page_count else "") + f" ({d.file_name})" for n, d in enumerate(scope, 1)]
    head = f"Các nguồn bạn đã chọn ({len(scope)}):" if lang == "vi" else f"The sources you selected ({len(scope)}):"
    return head + "\n" + "\n".join(lines)


def unlisted_message(names: List[str], scope: List[DocumentRecord], lang: str = "vi") -> str:
    sources = "; ".join(document_label(d) for d in scope)
    if lang != "vi":
        return (f"The question mentions {', '.join(names)}, which is not among the sources you selected ({sources}). I answer only from the "
                "selected sources: upload and select that company's report, or ask about the companies in the sources.")
    return (
        f"Câu hỏi nhắc đến {', '.join(names)}, nhưng không có trong các nguồn bạn đã chọn ({sources}). "
        "Tôi chỉ trả lời dựa trên các nguồn đã chọn: hãy tải lên và chọn thêm tài liệu của công ty đó, "
        "hoặc đặt câu hỏi về các công ty có trong nguồn."
    )
