import html
from bisect import bisect_left, bisect_right
import fitz  # PyMuPDF

from app.services.ingestion.postprocess.constants import FOOTNOTE_SYMBOLS, NAV_TITLE_KEY, SUPERSCRIPT_GAP, SUPERSCRIPT_RAISE, SUPERSCRIPT_RATIO, TEXT_FOLD, TOP_LINE_TOLERANCE, TRAILING_PUNCT
from app.services.ingestion.postprocess.tokens import is_marker, is_number, is_placeholder


# Ý nghĩa: chuẩn hóa một từ để so sánh giữa Markdown và PDF: bỏ thực thể HTML ("&amp;" -> "&"), chỉ giữ chữ-số, in hoa.
# Giữ vì: hai bên viết dấu câu khác nhau ("Place," / "Place"), từ chỉ gồm dấu câu ("&") ra chuỗi rỗng = không dùng làm bằng chứng.
def normalise(word: str) -> str:
    return "".join(c for c in html.unescape(word) if c.isalnum()).upper()


# Ý nghĩa: lỗi 16. Từ có hình dạng chỉ số chú thích: các nhóm "(x)" liền nhau (`is_marker`: "(a)", "(b)(c)", "(1)", chữ số trong ngoặc tối đa 2), số 1-2 chữ số nối bằng dấu phẩy ("3", "1,2") hoặc chuỗi toàn "*" / FOOTNOTE_SYMBOLS.
# Giữ vì: "10,000" (nhóm 3 chữ số), "2020" và "(104)" (số âm) không phải chỉ số; hình dạng chưa đủ để kết luận (số "3" là số thật khi in cùng cỡ), nên `sits_on` còn đòi cỡ chữ và vị trí.
def is_footnote_ref(token: str) -> bool:
    return ((is_marker(token) and not any(part[1:].isdigit() and len(part) > 3 for part in token.split(")")))
            or all(part.isdigit() and len(part) <= 2 for part in token.split(","))
            or (bool(token) and set(token) <= set("*") | FOOTNOTE_SYMBOLS))


# Ý nghĩa: lỗi 16. Từ `word` (một phần tử của `page.get_text("words")`) có in nhỏ như chỉ số chú thích so với từ `host` không, chỉ xét chiều cao và chiều dọc: tâm của `word` không cao hơn đầu hộp của `host` quá 1 điểm,
#   `word` cao không quá SUPERSCRIPT_RATIO lần `host`, và tâm của nó cao hơn tâm của `host` ít nhất SUPERSCRIPT_RAISE điểm; chỉ số chữ cái "(a)" còn nhận khi đáy của nó không thấp hơn đáy của `host`.
# Giữ vì: chỉ số in nhỏ nâng lên (JPM p136 "(43)" rồi "(a)", Coca-Cola 2017 p47 "1%" rồi "3") và chỉ số chữ cái nhỏ cùng đáy với số (JPM p128, p261: 6 pt cạnh 8 pt, không nâng) là hai kiểu in thật;
#   hình dạng "(chữ)" không thể là số nên không cần nâng lên, còn chữ số đơn thì cần nâng vì "3" in cùng cỡ cạnh một số khác là số thật.
def sits_on(word: tuple, host: tuple) -> bool:
    y0, y1, text = word[1], word[3], word[4]
    centre = (y0 + y1) / 2
    letters = is_marker(text) and not any(ch.isdigit() for ch in text)
    return (y1 > y0 and centre >= host[1] - 1.0 and y1 - y0 <= SUPERSCRIPT_RATIO * (host[3] - host[1])
            and ((host[1] + host[3]) / 2 - centre >= SUPERSCRIPT_RAISE or (letters and y1 <= host[3] + 0.5)))


# Ý nghĩa: lỗi 16. Từ PDF (`page.get_text("words")`) với mép phải của số đứng ngay trước mỗi chỉ số chú thích được kéo ra hết chỉ số (hộp của từ chỉ đổi mép phải, chữ không đổi). Số đứng trước = từ là số
#   hoặc từ giữ chỗ ("NM", "—") bên trái chỉ số, cách mép trái chỉ số không quá SUPERSCRIPT_GAP điểm, mà chỉ số in nhỏ theo `sits_on`; nhiều từ như vậy thì lấy từ gần nhất.
# Giữ vì: các luật gom cột theo khoảng ngang coi chỉ số căn trái ở vị trí cố định (cách số 3-14 điểm) là một cột giá trị riêng: JPM p136 thành 12-13 cột (6 cột "(a)" "(e)" xen kẽ), Coca-Cola p47 một cột
#   "3" "4" "5". Kéo mép số ra hết chỉ số làm chỉ số cùng cột giá trị (`value_columns`) và cùng ô; chữ không đổi nên mọi phép so chữ với ô Docling không đổi. Chỉ dùng cho `regrid_block`: `ghost_columns`
#   cần hộp gốc (tâm của số kéo dài có thể rơi vào ô chỉ số).
# Giới hạn: số đứng trước phải là số/từ giữ chỗ trong SUPERSCRIPT_GAP điểm: chỉ số đứng xa sau nhãn chữ ("Consumer & Business Banking" rồi "(d)" cách 70 điểm) không được gắn; cột chứa chúng
#   được `regrid_block` bỏ qua (`ghost`) và gộp ở mức Markdown (`merge_ghost_columns`).
def glue_superscripts(words: list) -> list:
    by_right = sorted(range(len(words)), key=lambda k: words[k][2])
    rights = [words[k][2] for k in by_right]
    reach: dict[int, float] = {}
    for i, word in enumerate(words):
        if not is_footnote_ref(word[4].translate(TEXT_FOLD)):
            continue
        hosts = [(word[0] - words[k][2], k) for k in by_right[bisect_left(rights, word[0] - SUPERSCRIPT_GAP):bisect_right(rights, word[0] + 1.0)]
                 if sits_on(word, words[k])
                 and (is_number(words[k][4].translate(TEXT_FOLD)) or is_placeholder(words[k][4].translate(TEXT_FOLD)))]
        if hosts:
            nearest = min(hosts)[1]
            reach[nearest] = max(reach.get(nearest, 0.0), word[2])
    return [(word[0], word[1], max(word[2], reach.get(i, word[2])), *word[3:]) for i, word in enumerate(words)]


# Ý nghĩa: bằng chứng của MỘT trang PDF: tập từ của trang, các cặp từ kề nhau trên cùng một dòng chữ, các cặp "từ cuối dòng / từ đầu
#   dòng kế" (cùng khối), và với mỗi cặp (chữ hoa đơn, đuôi) kề nhau trên một dòng thì tỉ lệ chiều cao đuôi / chữ đầu.
#   Thêm `nav_key`: chữ (đã chuẩn hóa) của dòng trên cùng của trang nếu có liên kết nội bộ phủ lên hoặc là "Table of Contents", ngược lại
#   rỗng (lỗi 4).
# Giữ vì: đây là chỗ duy nhất đọc PDF (bằng PyMuPDF `page.get_text("words")`); mọi luật nối dựa vào các tập này.
# Giới hạn: so khớp theo cặp từ cả trang, không theo tọa độ; "cỡ chữ" là chiều cao hộp bao của từ (cùng font thì tỉ lệ bằng tỉ lệ cỡ chữ),
#   không đọc cỡ chữ gốc của font.
# Giới hạn: so khớp theo cặp từ cả trang nên cặp lặp lại ở nơi khác trên trang cùng cho kết quả (cặp hiếm gặp hai kiểu cùng lúc
#   thì tỉ lệ lấy lớn nhất = bảo thủ, không nối).
class PageEvidence:
    def __init__(self, page: "fitz.Page"):
        self.same_line: set[tuple[str, str]] = set()
        self.next_line: set[tuple[str, str]] = set()
        self.size_ratio: dict[tuple[str, str], float] = {}
        self.words: set[str] = set()
        self.nav_key = ""
        lines: dict[tuple[int, int], list[tuple[str, float]]] = {}
        page_words = self.boxes = page.get_text("words")
        if page_words:
            top = min(word[1] for word in page_words)
            first_line = sorted((word for word in page_words if word[1] - top < TOP_LINE_TOLERANCE), key=lambda word: word[0])
            key = normalise("".join(word[4] for word in first_line))
            box = fitz.Rect(first_line[0][0], top, max(word[2] for word in first_line), max(word[3] for word in first_line))
            if key == NAV_TITLE_KEY or any(link["kind"] == fitz.LINK_GOTO and link["from"].intersects(box) for link in page.get_links()):
                self.nav_key = key
        for x0, y0, x1, y1, text, block, line, _word in page_words:
            lines.setdefault((block, line), []).append((text, y1 - y0))
            if normalise(text):
                self.words.add(normalise(text))
        keys = list(lines)
        for words in lines.values():
            for (a, ha), (b, hb) in zip(words, words[1:]):
                na, nb = normalise(a), normalise(b)
                if not na or not nb:
                    continue
                self.same_line.add((na, nb))
                if len(na) == 1 and a.isupper() and nb.isalpha() and b.strip(TRAILING_PUNCT).isupper() and ha > 0:
                    ratio = hb / ha
                    self.size_ratio[(na, nb)] = max(ratio, self.size_ratio.get((na, nb), 0.0))
        for first, second in zip(keys, keys[1:]):
            if first[0] == second[0]:
                last, head = normalise(lines[first][-1][0]), normalise(lines[second][0][0])
                if last and head:
                    self.next_line.add((last, head))


# Ý nghĩa: lấy bằng chứng của trang pdf_page (đếm từ 1), nhớ lại để không đọc PDF hai lần; không có PDF thì trả None.
def page_evidence(pdf, cache: dict, pdf_page: int):
    if pdf is None or not 1 <= pdf_page <= len(pdf):
        return None
    if pdf_page not in cache:
        cache[pdf_page] = PageEvidence(pdf[pdf_page - 1])
    return cache[pdf_page]
