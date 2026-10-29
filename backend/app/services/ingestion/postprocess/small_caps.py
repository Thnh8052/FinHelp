from collections import Counter

from app.services.ingestion.postprocess.constants import LEADING_PUNCT, LETTER_SPACED_MIN_RUN, SMALL_CAPS_MAX_RATIO, TRAILING_PUNCT
from app.services.ingestion.postprocess.evidence import normalise


# Ý nghĩa: một token có thể là chữ hoa đầu của small caps không: đúng một chữ ASCII hoa, chỉ có thể kèm dấu mở đầu "(" hoặc nháy kép.
# Giữ vì: "I," (dấu phẩy sau) và "'S" (nháy đơn) là từ khác; không bao giờ là chữ đầu của một từ bị tách.
def small_caps_head(token: str) -> str:
    core = token.lstrip(LEADING_PUNCT)
    return core if len(core) == 1 and core.isascii() and core.isupper() else ""


# Ý nghĩa: một token có thể là phần đuôi small caps không: chữ ASCII hoa liền nhau (cho phép dấu câu cuối); trả (chữ, dấu cuối).
def small_caps_tail(token: str) -> tuple[str, str]:
    core = token.rstrip(TRAILING_PUNCT)
    ok = bool(core) and core.isascii() and core.isalpha() and core.isupper()
    return (core, token[len(core):]) if ok else ("", "")


# Ý nghĩa: đếm từ (chữ thường) của cả tài liệu, bỏ các cặp ứng viên small caps trước khi đếm để phần đuôi vỡ không tự làm chứng.
# Giữ vì: chỉ phục vụ bằng chứng (c) của lỗi 7, khi PDF không có bằng chứng nào khác.
def build_vocabulary(texts: list[str]) -> Counter:
    vocabulary: Counter = Counter()
    for text in texts:
        for line in text.split("\n"):
            tokens = line.split()
            i = 0
            while i < len(tokens):
                if small_caps_head(tokens[i]) and i + 1 < len(tokens) and small_caps_tail(tokens[i + 1])[0]:
                    i += 2
                    continue
                word = "".join(c if c.isalpha() else " " for c in tokens[i]).lower()
                vocabulary.update(word.split())
                i += 1
    return vocabulary


# Ý nghĩa: dòng có toàn chữ hoa không (mọi từ có chữ cái đều viết hoa); tiêu đề small caps thường như vậy.
def is_all_caps(tokens: list[str]) -> bool:
    letters = ["".join(c for c in token if c.isalpha()) for token in tokens]
    return all(word.isupper() for word in letters if word)


# Ý nghĩa: lỗi 7. Nối (chữ hoa đơn, phần đuôi) theo ba bằng chứng (a) cỡ chữ PDF, (b) từ ghép có sẵn trong PDF, (c) từ vựng tài liệu;
#   nối chuỗi chữ giãn cách ("I N D E X"). Đếm vào `merged` (kèm bằng chứng) các chỗ đã nối, `kept` các ứng viên giữ nguyên.
# Giữ vì: BM25/khớp từ khóa "MGM Resorts International" không khớp "R ESORTS". (a) và (b) lấy từ PDF nên tên chỉ có dạng small caps
#   ("B EMIS") và đuôi trùng từ thông dụng ("F ACT", "P ART", "T RUST") vẫn xử lý đúng.
# Giới hạn: không có PDF thì chỉ còn (c). (c) cố ý bảo thủ: ca lớp chữ PDF có dấu cách thật cùng cỡ mà đuôi trùng từ thông dụng của tài
#   liệu ("F ACT") sẽ không được nối. Chữ giãn cách chỉ nối khi >= LETTER_SPACED_MIN_RUN chữ, không phải một chữ lặp ("X X X X").
def fix_small_caps(text: str, evidence, vocabulary: Counter, merged: Counter, kept: Counter) -> str:
    out_lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("|"):
            # Hàng bảng: sửa từng ô (tên trong bảng chữ ký cũng bị tách), giữ nguyên các dấu "|" và phần đệm của ô.
            cells = line.split("|")
            out_lines.append("|".join(merge_small_caps(cell, evidence, vocabulary, merged, kept) for cell in cells))
        else:
            out_lines.append(merge_small_caps(line, evidence, vocabulary, merged, kept))
    return "\n".join(out_lines)


# Ý nghĩa: sửa small caps trong MỘT đoạn chữ (một dòng văn hoặc một ô bảng), giữ nguyên khoảng trắng đầu và cuối đoạn.
# Giữ vì: tách khỏi fix_small_caps để dùng chung cho dòng văn và ô bảng; ngữ cảnh "cả dòng viết hoa" tính trong phạm vi đoạn.
def merge_small_caps(segment: str, evidence, vocabulary: Counter, merged: Counter, kept: Counter) -> str:
    body = segment.strip(" ")
    if not body:
        return segment
    lead = segment[:len(segment) - len(segment.lstrip(" "))]
    trail = segment[len(segment.rstrip(" ")):]
    tokens = body.split(" ")
    result: list[str] = []
    i = 0
    while i < len(tokens):
        head = small_caps_head(tokens[i])
        run = 0
        while head and i + run < len(tokens) and small_caps_head(tokens[i + run]) and tokens[i + run].isalpha():
            run += 1
        if run >= LETTER_SPACED_MIN_RUN and len({tokens[i + k] for k in range(run)}) > 1:
            word = "".join(tokens[i:i + run])
            merged[f"{' '.join(tokens[i:i + run])} -> {word}"] += 1
            result.append(word)
            i += run
            continue
        tail, trailing = small_caps_tail(tokens[i + 1]) if head and i + 1 < len(tokens) else ("", "")
        if head and tail:
            key = (normalise(head), normalise(tail))
            proof = ""
            if evidence is not None:
                ratio = evidence.size_ratio.get(key)
                if ratio is not None and ratio <= SMALL_CAPS_MAX_RATIO:
                    proof = "size"
                elif (head + tail).upper() in evidence.words and key not in evidence.same_line:
                    proof = "pdf_word"
            if not proof and is_all_caps(tokens) and vocabulary[(head + tail).lower()] and not vocabulary[tail.lower()]:
                proof = "vocabulary"
            if proof:
                prefix = tokens[i][:len(tokens[i]) - 1]
                merged[f"{head} {tail} -> {head}{tail} [{proof}]"] += 1
                result.append(prefix + head + tail + trailing)
                i += 2
                continue
            kept[f"{head} {tail}"] += 1
        result.append(tokens[i])
        i += 1
    return lead + " ".join(result) + trail
