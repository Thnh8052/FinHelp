from app.services.ingestion.postprocess.constants import NUMBER_CHARS, VALUE_PREFIXES, VALUE_SUFFIXES


# Ý nghĩa: từ có phải một phần của giá trị không: có chữ số, ký hiệu tiền/phần trăm/ngoặc, hoặc chỉ gồm gạch ("-" = không có giá trị).
def is_value_token(token: str) -> bool:
    return any(ch.isdigit() for ch in token) or token in VALUE_PREFIXES or token in VALUE_SUFFIXES or set(token) <= {"-"}


# Ý nghĩa: từ trong vùng giá trị có phải chữ (ô chữ, không phải số, ký hiệu hay chú thích) không: có chữ thường nằm ngoài ngoặc đơn.
# Giữ vì: cột số chứa chú thích và viết tắt ("(a)", "(f)(g)", "NM", "N/A", "NA", "*") không có chữ thường ngoài ngoặc; ô chữ ("Various", "years",
#   "Yes", tên người) thì có, và ô chữ xuống dòng ngay trong một hàng nên một dòng chữ PDF không còn là một hàng (lỗi 13).
def is_text_word(token: str) -> bool:
    depth = 0
    for ch in token:
        depth += (ch == "(") - (ch == ")")
        if ch.islower() and depth <= 0:
            return True
    return False


# Ý nghĩa: từ có phải số thuần không: là giá trị (is_value_token) và chỉ gồm chữ số, ký hiệu tiền, phẩy, chấm, phần trăm, ngoặc, gạch (NUMBER_CHARS).
# Giữ vì: ngày "5/31/2019;", mã "88-6016617/001", quý "1H" có chữ số nhưng không phải số: ô chứa chúng là ô chữ xuống dòng, không phải ô giá trị.
def is_number(token: str) -> bool:
    return is_value_token(token) and set(token) <= NUMBER_CHARS


# Ý nghĩa: từ giữ chỗ cho giá trị ("N/A", "NM", "*", "(a)", "&"): không có chữ số và không có chữ thường ngoài ngoặc đơn.
def is_placeholder(token: str) -> bool:
    return not any(ch.isdigit() for ch in token) and not is_text_word(token)


# Ý nghĩa: từ có phải chỉ số chú thích không: một hay nhiều nhóm "(x)" liền nhau, mỗi nhóm 1-3 ký tự trong ngoặc: "(7)", "(a)", "(iii)", "(f)(g)"; "(loss)" và số âm "(1,010)" thì không.
def is_marker(token: str) -> bool:
    parts = token.split(")")
    return len(parts) > 1 and parts[-1] == "" and all(part.startswith("(") and 1 <= len(part) - 1 <= 3 and "," not in part for part in parts[:-1])


# Ý nghĩa: lỗi 23. Chỉ các chữ cái của `text` (in hoa): khóa so "cùng một dòng in ở nhiều trang" mà không bị số trang làm khác ("12 | 2022 Annual Report" và "13 | ..." cùng khóa).
def letters(text: str) -> str:
    return "".join(c for c in text if c.isalpha()).upper()
