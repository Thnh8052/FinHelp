"""Replies that need no retrieval and no generation (not charged to the user's quota), and the fixed answer texts."""
from typing import Any, Dict, List, Optional

from app.modules.documents.document import DocumentRecord
from app.modules.chat.scope import document_label

# Appended by code to an answer that found nothing (docs/Version_3/fail_cases.md, S2): never suggests a document outside the selected sources
CHECK_SOURCES = {"vi": "Hãy kiểm tra lại các nguồn đã chọn hoặc tài liệu đã tải lên.",
                 "en": "Please check the selected sources or the uploaded documents."}
# Appended to the answer of a "search again" click that still found nothing, or not enough (S3/S5): there is no further button
RETRY_APOLOGY = {"vi": "Xin lỗi, trong giới hạn hiện tại hệ thống chưa tìm được đủ thông tin này. " + CHECK_SOURCES["vi"],
                 "en": "Sorry, within its current limits the system could not find enough of this information. " + CHECK_SOURCES["en"]}
# Appended to the answer of a "search again" click that found the information but still has figures or citations it could not verify (the "⚠️" line):
# the problem is the figures, never "not found" (behavior check 17/11/2026, tests/test_failure_replies.py)
RETRY_FIGURES_APOLOGY = {"vi": "Xin lỗi, sau lần tìm lại vẫn còn chi tiết trong câu trả lời chưa kiểm chứng được với đoạn trích (đánh dấu ⚠️). "
                               "Hãy đối chiếu với trang được trích trước khi sử dụng.",
                         "en": "Sorry, after searching again some details of the answer still could not be verified against the excerpts (marked ⚠️). "
                               "Please check them against the cited pages before using them."}
# A step of the search was dropped for time or failure (retrieval_step degraded): said without naming any component, and without naming a button
# (its label follows the interface language, this line the question's), in place of "check your sources": the sources are not the cause
DEGRADED_NOTE = {"vi": "Lần tìm này có thể chưa đầy đủ vì hệ thống đang chậm. Bạn có thể thử tìm lại sau ít phút.",
                 "en": "This search may be incomplete because the system was slow. You can try searching again in a few minutes."}
NO_DATA_ANSWER = {"vi": "Không tìm thấy dữ liệu tài chính phù hợp trong tài liệu của notebook này. " + CHECK_SOURCES["vi"],
                  "en": "No matching financial data was found in this notebook's documents. " + CHECK_SOURCES["en"]}


def _cells(line: str) -> List[str]:
    return [" ".join(c.split()) for c in line.strip().strip("|").split("|")]


def excerpt_preview(content: str, rows: int = 6, chars: int = 400) -> str:
    """A readable piece of a chunk for the replies written without the model (outage, cut reply: tests/test_excerpt_preview.py). A table: its title lines,
    its header and its first `rows` rows that hold a figure, as a compact markdown table (the first 400 characters of a table were only its header and
    a long line of dashes). A text: cut at the last sentence end within `chars`, else at a word with "…"."""
    lines = [l for l in content.splitlines() if l.strip()]
    table = [l for l in lines if l.lstrip().startswith("|")]
    if len(table) >= 2:
        title = [l.strip().lstrip("#").strip() for l in lines[: lines.index(table[0])]][:3]
        head = _cells(table[0])
        body = [_cells(l) for l in table[1:] if not set(l.replace("|", "").strip()) <= {"-", ":", " "}]
        body = [r for r in body if any(ch.isdigit() for c in r[1:] for ch in c)][:rows]
        row = lambda cells: "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"
        return "\n".join(([" — ".join(title), ""] if title else []) + [row(head), "|" + "---|" * len(head)] + [row(r) for r in body])
    text = " ".join(" ".join(l.strip().lstrip("#").strip() for l in lines).split())
    if len(text) <= chars:
        return text
    cut = text[:chars]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[: end + 1] if end > chars // 3 else cut[: cut.rfind(" ")].rstrip() + "…"


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
