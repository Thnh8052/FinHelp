from collections import Counter

from app.services.ingestion.postprocess.constants import BULLET_TOKENS, STRUCTURE_PREFIXES
from app.services.ingestion.postprocess.evidence import normalise


# Ý nghĩa: dòng có phải mở đầu một mục danh sách không: gạch đầu dòng/dấu chấm tròn, "1." "12)" "a." "(a)" "(iii)" "(12)".
# Giữ vì: khi PDF không có bằng chứng, mục danh sách không được nối vào mục trước.
# Giới hạn: "(702)" (mã vùng điện thoại, ba chữ số) không phải đầu mục: trong ngoặc cho tối đa 2 chữ số hoặc 3 chữ cái.
def starts_list_item(line: str) -> bool:
    parts = line.split()
    if not parts:
        return False
    token = parts[0]
    if token in BULLET_TOKENS:
        return True
    if token[0] == "(" and token[-1] == ")" and len(token) > 2:
        inner = token[1:-1]
        return (inner.isdigit() and len(inner) <= 2) or (inner.isalpha() and len(inner) <= 3)
    if token[-1] in ".)" and len(token) > 1:
        inner = token[:-1]
        return (inner.isdigit() and len(inner) <= 3) or (inner.isalpha() and len(inner) == 1)
    return False


# Ý nghĩa: quyết định nối hai dòng liền nhau hay giữ ngắt dòng; trả "join" / "keep" và lý do để thống kê.
# Giữ vì: một chỗ duy nhất cho luật lỗi 6. Cùng một dòng PDF -> nối. Dòng trước có hai dấu cách cuối (dấu hiệu của lỗi) mà PDF không
#   có bằng chứng -> nối, trừ khi dòng sau là mục danh sách hoặc PDF nói hai từ ở hai dòng khác nhau (ngắt dòng thật).
def decide(previous: str, following: str, evidence) -> tuple[str, str]:
    if previous.lstrip().startswith(STRUCTURE_PREFIXES) or following.lstrip().startswith(STRUCTURE_PREFIXES):
        return "keep", "structure"
    pair = (normalise(previous.split()[-1]), normalise(following.split()[0]))
    known = all(pair)
    if evidence is not None and known and pair in evidence.same_line:
        return "join", "same_line"
    hard = previous.endswith("  ")
    if not hard:
        return "keep", "single_newline_not_same_line"
    if starts_list_item(following):
        return "keep", "list_item"
    if evidence is not None and known and pair in evidence.next_line:
        return "keep", "real_line_break"
    return "join", "hard_break_no_evidence"


# Ý nghĩa: lỗi 6. Đi qua từng cặp dòng liền nhau (cả hai không trống) và nối theo `decide`; đếm số lần nối/giữ theo lý do.
# Giữ vì: mỗi từ một dòng làm hỏng tách câu, tốn token và hạ điểm tương đồng embedding (MGM p1: 257 dòng cho một đoạn ngắn).
# Giới hạn: bằng chứng PDF theo cặp từ cả trang; trang không có PDF chỉ nối được ca ngắt dòng cứng.
def join_broken_lines(text: str, evidence, counts: Counter) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        if out and out[-1].strip() and line.strip():
            action, reason = decide(out[-1], line, evidence)
            counts[f"{action}:{reason}"] += 1
            if action == "join":
                out[-1] = out[-1].rstrip() + " " + line.lstrip()
                continue
        out.append(line)
    return "\n".join(out)


# Ý nghĩa: gộp mọi chuỗi khoảng trắng trong dòng văn thành một dấu cách (giữ thụt lề đầu dòng, bỏ khoảng trắng cuối) và gộp dòng
#   trắng liên tiếp thành một; hàng bảng giữ nguyên.
# Giữ vì: phần dư dấu cách của lỗi 6 ("investing  cash  flows") và chuỗi 22 dòng trắng ở MGM p1.
# Giới hạn: chạy SAU join_broken_lines (hàm kia cần hai dấu cách cuối dòng để nhận ra ngắt dòng cứng).
def tidy_spaces(text: str) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        if not line.lstrip().startswith("|"):
            indent = line[:len(line) - len(line.lstrip(" "))]
            line = indent + " ".join(line.split())
        if line.strip() or not out or out[-1].strip():
            out.append(line)
    return "\n".join(out)
