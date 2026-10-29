from app.services.ingestion.postprocess.constants import BOUNDARY_MARGIN, NUMERIC_TABLE_MIN_SHARE, PHRASE_GAP, SYMBOL_CELLS, TEXT_FOLD, VALUE_GAP_TOLERANCE, VALUE_LINE_TOLERANCE, VALUE_PREFIXES, VALUE_SUFFIXES
from app.services.ingestion.postprocess.tokens import is_marker, is_number, is_placeholder, is_value_token


# Ý nghĩa: ghép một khối bảng Markdown (các hàng đã tách ô, hàng 1 là dòng "---") với lưới Docling của nó; trả lưới hoặc None.
# Giữ vì: số hàng header = số hàng lưới - số hàng thân, nên chỉ cần so các hàng thân (từ cuối lưới) nguyên văn, cùng số cột; với header một
#   hàng so luôn hàng đó. Bảng một khối chỉ có header (không hàng thân) vì vậy cũng phải khớp header, không ghép bằng số cột suông.
# Giới hạn: header nhiều hàng (Docling gộp bằng " - ") không so lại; hàng thân khớp nguyên văn đã đủ để loại ghép nhầm. Khối chỉ có
#   header của bảng nhiều hàng không ghép (không có hàng thân để làm bằng chứng) -> giữ nguyên.
def match_grid(rows: list[list[str]], candidates: list):
    body = rows[2:]
    for grid in candidates:
        if not grid or len(grid[0]) != len(rows[0]) or len(body) > len(grid):
            continue
        if not body and len(grid) != 1:
            continue
        if len(grid) - len(body) == 1 and [text for text, _ in grid[0]] != rows[0]:
            continue
        if all([text for text, _ in grid_row] == cells for grid_row, cells in zip(grid[len(grid) - len(body):], body)):
            return grid
    return None


# Ý nghĩa: cột `col` của một nhóm hàng lưới (một hàng thân, hoặc các hàng header gộp thành một dòng) có phải toàn bản sao của ô gộp ngang
#   không: có chữ và mọi ô có chữ đều có ô gốc ở cột khác `col`.
# Giữ vì: cột mà một ô có ô gốc ngay tại đó (nhãn riêng, ví dụ "Year ended December 31, - 2020" ở header nhiều hàng) giữ nguyên toàn bộ.
def is_span_copy(rows: list, col: int) -> bool:
    slots = [row[col] for row in rows if row[col][0]]
    return bool(slots) and all(start != col for _, start in slots)


# Ý nghĩa: cột `col` của các hàng thân có phải cột ký hiệu không: có ô chữ, không ô nào có chữ số, và ô là ký hiệu (SYMBOL_CELLS) nhiều hơn
#   mọi ô khác cộng lại.
# Giữ vì: "$" tách khỏi số thành cột riêng ("$ | 2,180"); đa số chứ không phải tất cả vì hàng header lặp trong thân ("High", AMD p32) và "-"
#   (AMD p57) nằm lẫn trong cột. Không có chữ số vì cột có số là cột dữ liệu, không bao giờ bỏ nhãn của nó.
def is_symbol_column(body: list, col: int) -> bool:
    cells = [row[col][0] for row in body if row[col][0]]
    return sum(cell in SYMBOL_CELLS for cell in cells) * 2 > len(cells) and not any(ch.isdigit() for cell in cells for ch in cell)


# Ý nghĩa: lỗi 11. Trong các cột bản sao của header (`copies`), cột nào nhận lại nhãn từ cột ký hiệu kề trái nó: {cột số: cột ký hiệu}.
# Giữ vì: ô gộp "2020" phủ cả cột "$" và cột số, `unspan_tables` giữ chữ ở ô đầu nên cột "$" có tên còn cột số liệu thật trống tên (Corning
#   p40). Điều kiện: cột kề trái không phải bản sao (đang giữ nhãn) và là cột ký hiệu, cột số có chữ số. Không mất nhãn nào: ô gộp bắt đầu
#   trước cột số thì cũng phủ cột kề trái, nên cột ký hiệu có đủ nhãn của cột số (đo 27/27); nhãn chuyển sang là chữ đầy đủ của cột ký hiệu.
# Giới hạn: chỉ xét cột kề trái; cột ký hiệu và cột số cách nhau một cột (ví dụ cột chú thích ở giữa) không chuyển. Cột số chỉ gồm chỉ số
#   chú thích "(1)" cũng có chữ số nên vẫn nhận nhãn.
def label_hosts(body: list, copies: list[int]) -> dict[int, int]:
    hosts: dict[int, int] = {}
    for col in copies:
        host = col - 1
        if host >= 0 and host not in copies and is_symbol_column(body, host) and any(ch.isdigit() for row in body for ch in row[col][0]):
            hosts[col] = host
    return hosts


# Ý nghĩa: lý do một bảng không được dựng lại cột (lỗi 12); `reason` là khóa đếm trong báo cáo.
class RegridSkip(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


# Ý nghĩa: cột đầu tiên có giá trị trong các hàng thân (ô có chữ số hoặc ký hiệu tiền); các cột trước nó là cột nhãn. None nếu không có.
def first_value_column(body: list, ncols: int):
    return next((col for col in range(1, ncols) if any(any(ch.isdigit() for ch in row[col][0]) or row[col][0] in SYMBOL_CELLS for row in body)), None)


# Ý nghĩa: bảng có phải bảng số liệu không: ít nhất NUMERIC_TABLE_MIN_SHARE ô giá trị chỉ gồm từ của giá trị.
def is_numeric_table(body: list, first: int, ncols: int) -> bool:
    texts = [row[col][0] for row in body for col in range(first, ncols) if row[col][0]]
    return bool(texts) and sum(all(is_value_token(token) for token in text.split()) for text in texts) >= NUMERIC_TABLE_MIN_SHARE * len(texts)


# Ý nghĩa: gom các từ PDF của một hàng (x0, x1, chữ) thành giá trị theo thứ tự trái sang phải: "$" và "(" dính vào từ kế tiếp, "%" và ")"
#   dính vào từ liền trước. Trả [(x0, x1, [từ])] với chữ đã qua TEXT_FOLD.
def group_value_words(words: list) -> list:
    groups: list = []
    for x0, x1, text in sorted(words):
        text = text.translate(TEXT_FOLD)
        if groups and (groups[-1][2][-1] in VALUE_PREFIXES or text in VALUE_SUFFIXES):
            groups[-1] = (min(groups[-1][0], x0), max(groups[-1][1], x1), groups[-1][2] + [text])
        else:
            groups.append((x0, x1, [text]))
    return groups


# Ý nghĩa: các cột giá trị của bảng = hợp các khoảng ngang [x0, x1] của mọi giá trị ở mọi hàng, hai khoảng cách nhau không quá
#   `gap` (mặc định VALUE_GAP_TOLERANCE) thì cùng một cột; trả danh sách [x0, x1] từ trái sang phải.
# Giữ vì: số căn lề phải nên các số của một cột chồng lên nhau; "$" đã dính vào số của nó (group_value_words) nên không còn bắc cầu sang
#   cột kề trái dù chỉ cách số cột đó 8 điểm (Corning p76).
def value_columns(groups: list, gap: float = VALUE_GAP_TOLERANCE) -> list:
    columns: list = []
    for x0, x1 in sorted((group[0], group[1]) for group in groups):
        if columns and x0 <= columns[-1][1] + gap:
            columns[-1][1] = max(columns[-1][1], x1)
        else:
            columns.append([x0, x1])
    return columns


# Ý nghĩa: từ PDF của từng hàng giá trị: {hàng lưới: [(x0, x1, chữ)]}; ném RegridSkip nếu chữ PDF không khớp chữ các ô giá trị của Docling.
#   Hàng trải trên nhiều dòng PDF mà số chỉ nằm ở một dòng (chữ xuống dòng) không phải lỗi: ném `wrapped` (không thử dựng lại hàng, lỗi 13). Hàng chỉ có một ô ở cột nhãn
#   mà ô đó là số (không phải năm) là giá trị bị Docling đặt nhầm cột (AES p39 tổng "3,390"): `stray_word`.
# Giữ vì: dải dọc của hàng là hợp hộp bao các ô có chữ của hàng đó; vùng ngang là từ ô giá trị trái nhất đến phải nhất (trang JPM hai cột: bảng
#   ở cột trái, đoạn văn ở cột phải cùng độ cao); từ nằm trong hộp bao của ô nhãn là chữ nhãn (nhãn dài lấn sang vùng giá trị), không tính.
#   Chữ của hàng (bỏ khoảng trắng, "—" thành "-") phải bằng chữ các ô giá trị của Docling: lệch là Docling đặt giá trị sang hàng khác (nhãn hai
#   dòng bị chia thành hai hàng, AES p135 "Other / liabilities:" có 120 ở hàng "liabilities:"), không có gì đáng tin để dựng lại cột.
def value_words(cells: tuple, headers: int, first: int, page_words: list) -> dict:
    body = [c for c in cells if c.row >= headers and c.text]
    values = [c for c in body if c.col >= first]
    if not values or any(c.row_span > 1 or c.col_span > 1 for c in values):
        raise RegridSkip("span")
    bands: dict[int, list[float]] = {}
    for c in body:
        if any(v.row == c.row for v in values):
            band = bands.setdefault(c.row, [c.t, c.b])
            band[0], band[1] = min(band[0], c.t), max(band[1], c.b)
    left, right = min(c.l for c in values) - 1.5, max(c.r for c in values) + 1.5
    top, bottom = min(b[0] for b in bands.values()) - 1, max(b[1] for b in bands.values()) + 1
    labels = [c for c in body if c.col < first]
    found: dict[int, list] = {row: [] for row in bands}
    for x0, y0, x1, y1, text, *_ in page_words:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if not left <= cx <= right or not top <= cy <= bottom or any(c.l <= cx <= c.r and c.t <= cy <= c.b for c in labels):
            continue
        inside = [row for row, (lo, hi) in bands.items() if lo - 1 <= cy <= hi + 1]
        if not inside:
            raise RegridSkip("stray_word")
        row = min(inside, key=lambda row: abs(cy - sum(bands[row]) / 2))
        found[row].append((x0, x1, text, cy))
    wrapped = False
    for row, words in found.items():
        if sorted("".join("".join(c.text for c in values if c.row == row).split())) != sorted("".join(w[2] for w in words).translate(TEXT_FOLD)):
            raise RegridSkip("tokens")
        if words and max(w[3] for w in words) - min(w[3] for w in words) > VALUE_LINE_TOLERANCE:
            if numeric_lines(words) > 1:
                raise RegridSkip("multiline")
            wrapped = True
    for row in {c.row for c in body}:
        alone = [c for c in body if c.row == row]
        is_year = len(alone) == 1 and alone[0].text.isdigit() and len(alone[0].text) == 4
        if len(alone) == 1 and alone[0].col < first and not is_year and any(ch.isdigit() for ch in alone[0].text) \
                and all(is_number(token) for token in alone[0].text.translate(TEXT_FOLD).split()):
            raise RegridSkip("stray_word")
    if wrapped:
        raise RegridSkip("wrapped")
    return {row: [(x0, x1, text) for x0, x1, text, _ in words] for row, words in found.items()}


# Ý nghĩa: số dòng PDF có ô số (cụm chữ gồm toàn số, kể cả gạch "—" là không có giá trị, không tính từ giữ chỗ) trong các từ (x0, x1, chữ, cy) của một hàng Docling.
# Giữ vì: hàng Docling trải trên nhiều dòng PDF chỉ là lỗi gộp hàng khi có số ở từ hai dòng trở lên ("967 140"); chữ xuống dòng của ô chữ ("Landfill" / "Gas", tiểu sử lãnh đạo
#   nhiều dòng cạnh một số tuổi) là hàng đúng, và dựng lại từ dòng PDF làm hỏng chúng (tên căn giữa lệch nửa dòng so với tuổi: Adobe p16, Boeing p127).
def numeric_lines(words: list) -> int:
    lines: list = []
    for word in sorted(words, key=lambda word: word[3]):
        if lines and word[3] - lines[-1][-1][3] <= VALUE_LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return sum(any(numeric and any(is_number(token.translate(TEXT_FOLD)) for x0, _, token, _ in line if p0 <= x0 <= p1) for p0, p1, numeric in phrase_cells([w[:3] for w in line]))
               for line in lines)


# Ý nghĩa: khoảng cách ngang từ tâm `x` đến một cột [x0, x1] (0 nếu nằm trong cột).
def distance_to_column(x: float, column: list) -> float:
    return 0.0 if column[0] <= x <= column[1] else min(abs(x - column[0]), abs(x - column[1]))


# Ý nghĩa: các cụm chữ của một dòng: các từ (x0, x1, chữ) cách nhau không quá PHRASE_GAP là một cụm; trả [(x0, x1, là cụm số)] với cụm số = mọi từ là số hoặc từ giữ chỗ.
# Giữ vì: chữ xuống dòng của ô chữ cũng chứa số ("Chief Executive Officer since December 2005.", "13 plans are closed ...") nhưng số đó đứng liền chữ trong cùng cụm;
#   phân loại theo cụm trên PDF, không theo ô Docling, vì Docling gộp ghi chú vào ô số ("(In millions) $ 51", AMD p87).
def phrase_cells(words: list) -> list:
    cells: list = []
    for x0, x1, token in sorted(words):
        if cells and x0 - cells[-1][-1][1] <= PHRASE_GAP:
            cells[-1].append((x0, x1, token))
        else:
            cells.append([(x0, x1, token)])
    return [(cell[0][0], cell[-1][1], all(is_number(token.translate(TEXT_FOLD)) or is_placeholder(token.translate(TEXT_FOLD)) for _, _, token in cell)) for cell in cells]


# Ý nghĩa: nhãn `label` có phải phần nối tiếp của nhãn `above` ở dòng trên không: từ đầu bắt đầu bằng chữ thường (sau dấu "(" nếu không phải chỉ số chú thích: "(loss) (5)"),
#   còn nhãn trên không kết thúc bằng dấu hai chấm (tiêu đề nhóm, kể cả khi theo sau là chỉ số chú thích).
# Giữ vì: tên hàng của báo cáo tài chính bắt đầu bằng chữ hoa, chữ số hoặc ký hiệu; đo trên mọi bảng số một cột nhãn: 366 trên 428 ca (dòng chỉ có nhãn + dòng kế bắt đầu bằng
#   chữ thường) có ô Docling đúng bằng chữ ghép, 62 ca còn lại phần lớn là nhãn xuống dòng mà ô Docling đã bị xé; ca sai là tên viết thường ("sPower") sau tiêu đề "...: (6)".
def continues_label(label: str, above: str) -> bool:
    words, above_words = label.split(), above.split()
    while above_words and is_marker(above_words[-1]):
        above_words.pop()
    first = words[0].lstrip("(") if words and not is_marker(words[0]) else ""
    return bool(first) and first[0].islower() and not (above_words and above_words[-1].endswith(":"))


# Ý nghĩa: khóa so chữ nhãn giữa PDF và ô nhãn Docling: bỏ mọi khoảng trắng, đổi gạch/nháy như Docling (TEXT_FOLD), giữ nguyên dấu câu và hoa thường.
# Giữ vì: Docling thêm/bớt dấu cách quanh chú thích ("(a)(b)" và "(a) (b)"), nhưng dấu câu phân biệt nhãn thật: khóa chỉ giữ chữ-số như `normalise`
#   làm "+100 bps" trùng "-100 bps" và "Gross margin" trùng "(gross margin %)" (JPM p139, Corning p26), nhãn bị gán nhầm cho nhau.
def label_key(text: str) -> str:
    return "".join(text.translate(TEXT_FOLD).split())


# Ý nghĩa: lỗi 13. Gom các từ PDF (tâm dọc, x0, x1, chữ) của thân bảng thành dòng chữ từ trên xuống, mỗi dòng sắp trái sang phải. Hai từ liền nhau
#   theo chiều dọc có tâm cách nhau quá VALUE_LINE_TOLERANCE là hai dòng; ném RegridSkip("lines") nếu một dòng bị nối chuỗi dài hơn dung sai đó.
# Giữ vì: chỉ số chú thích nhỏ ("(a)" của "NM (a)", JPM p139) lệch tâm 3,4 điểm so với chữ cùng dòng, còn nhãn xuống dòng có giá trị căn giữa
#   (A, giá trị, B; JPM p212 hai dòng nhãn cách nhau 7,4 điểm) có giá trị cách mỗi dòng 3,7 điểm nên nối chuỗi thành một dòng với chữ nhãn lẫn thứ
#   tự: không biết giá trị thuộc dòng nào thì không dựng lại. Đo trên 13.236 cụm từ của mọi bảng số: 99% lệch dưới 2,9 điểm, 64 cụm lệch từ 4 điểm trở lên.
def split_lines(words: list) -> list:
    lines: list = []
    for word in sorted(words):
        if lines and word[0] - lines[-1][-1][0] <= VALUE_LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    if any(line[-1][0] - line[0][0] > VALUE_LINE_TOLERANCE for line in lines):
        raise RegridSkip("lines")
    return [sorted(line, key=lambda word: word[1]) for line in lines]


# Ý nghĩa: chữ của ô nhãn Docling ứng với `text`: ô có cùng label_key, hoặc ô duy nhất có cùng bộ ký tự kể cả hoa thường và dấu câu (chỉ khác thứ tự chỉ số chú thích); không có thì chính `text`.
# Giữ vì: PDF đặt chỉ số chú thích theo vị trí ("Highlander (sPower OpCo B (1) )") còn Docling theo thứ tự trong tệp ("... B ) (1)"); hàng không đổi giữ nguyên chữ Docling.
#   Không so theo `normalise` vì nó bỏ hoa thường và dấu câu: "Available-for-sale securities:" (tiêu đề) trùng "available-for-sale securities" (hàng khác), JPM 10-Q p86.
def adopt_label(known: dict, text: str) -> str:
    if label_key(text) in known:
        return known[label_key(text)]
    same = {value for value in known.values() if sorted(label_key(value)) == sorted(label_key(text))}
    return same.pop() if len(same) == 1 else text


# Ý nghĩa: lỗi 13. Từ các dòng chữ của thân bảng [(nhãn theo cột, [dòng từ giá trị], trên, dưới)] dựng các hàng cùng dạng (trên, dưới = cy dòng đầu và dòng cuối). Mỗi dòng PDF là một
#   hàng, trừ khi ở một cột nhãn có ô Docling với đúng chữ ghép của nhiều dòng liền nhau (label_key) và chỉ dòng cuối của nhóm có giá trị: đó là nhãn xuống dòng, các dòng
#   chỉ có nhãn được nối xuôi vào dòng kế tiếp (giá trị căn đáy). Nhóm toàn dòng chỉ có nhãn (tiêu đề xuống dòng) cũng nối theo cùng bằng chứng, kể cả khi
#   dòng giá trị không có chữ nhãn nào (nhãn lệch dòng so với số: Coca-Cola 2017 p108 "Customer relationships 1"). Ở cột nhãn đầu còn nối khi mỗi dòng kế bắt đầu bằng chữ thường
#   (continues_label), vì ô Docling của nhãn xuống dòng thường bị xé. Nhãn lấy đúng chữ ô Docling.
#   Nối ngược (nhãn xuống dòng bên dưới hàng có giá trị, giá trị căn đầu) chỉ khi cả hai bằng chứng cùng chỉ: ô Docling có đúng chữ ghép, và dòng chỉ có nhãn cách hàng trên gần
#   hơn cách hàng dưới ít nhất BOUNDARY_MARGIN (JPM p274 "JPMorgan Chase - New" / "York State").
# Giữ vì: trong các bảng Docling đã đúng (707 + 137), 376 ô nhãn nối nhiều dòng PDF có giá trị ở dòng cuối, chỉ 24 ca ở dòng đầu và 9 ca ở giữa. Chỉ ô Docling thì chưa đủ để nối
#   ngược vì ô sai của Docling ("Real Estate Individuals and Individual", JPM p121; "Currency translation adjustment Other comprehensive income - cash", MGM p61) trông giống
#   hệt ô đúng; ở các ca đó dòng chỉ có nhãn nằm gần hàng dưới hơn. Bằng chứng lấy từ mọi ô nhãn của cột, không riêng chỗ đó: bảng lặp nhãn theo năm ("Other comprehensive
#   income - cash flow hedges" ở cả ba năm) nên khối năm bị Docling làm hỏng vẫn nối được nhờ ô đúng của khối năm khác.
# Giới hạn: nhãn xuống dòng mà không ô Docling nào giữ nguyên thì còn là một hàng chỉ có nhãn (giá trị vẫn đúng hàng). Nhãn căn giữa (cách đều hai hàng) không nối.
def wrap_rows(lines: list, known: list) -> list:
    rows: list = []
    i = 0
    while i < len(lines):
        end = i
        linked = True
        for j in range(i + 1, len(lines)):
            if any(lines[j - 1][1]):
                break
            linked = linked and continues_label(lines[j][0][0], lines[j - 1][0][0])
            parts = [[line[0][col] for line in lines[i:j + 1] if line[0][col]] for col in range(len(known))]
            wrapped = [col for col, texts in enumerate(parts) if len(texts) > 1]
            has_text = [col for col, texts in enumerate(parts) if texts]
            evidence = all(label_key("".join(parts[col])) in known[col] for col in (wrapped or has_text))
            if (wrapped and (evidence or (0 in wrapped and linked))) or (not wrapped and not any(lines[j][0]) and any(lines[j][1]) and evidence):
                end = j
        group = lines[i:end + 1]
        texts = [" ".join(line[0][col] for line in group if line[0][col]) for col in range(len(known))]
        words = [word for line in group for word in line[1]]
        if rows and any(rows[-1][1]) and not any(words):
            both = [col for col in range(len(known)) if rows[-1][0][col] and texts[col]]
            joined = [f"{rows[-1][0][col]} {texts[col]}" for col in range(len(known))]
            below = lines[end + 1][2] - group[-1][3] if end + 1 < len(lines) else None
            if both and all(label_key(joined[col]) in known[col] for col in both) and (below is None or group[0][2] - rows[-1][3] + BOUNDARY_MARGIN <= below):
                merged = [adopt_label(known[col], joined[col] if col in both else rows[-1][0][col] or texts[col]) for col in range(len(known))]
                rows[-1] = (merged, rows[-1][1], rows[-1][2], group[-1][3])
                i = end + 1
                continue
        rows.append(([adopt_label(known[col], text) for col, text in enumerate(texts)], words, group[0][2], group[-1][3]))
        i = end + 1
    return rows


# Ý nghĩa: lỗi 13. Gom dòng chữ nối tiếp (chữ xuống dòng của một ô: không có số, có chữ ở vùng giá trị hoặc ở cột nhãn thứ hai trở đi) vào dòng hàng của chúng; trả
#   [(nhãn theo cột, [dòng từ giá trị], trên, dưới)]. `raw`: [(nhãn theo cột, từ giá trị, cy, là dòng nối tiếp, chữ-số chuẩn hóa của dòng)]; `known`: {label_key: chữ} của ô nhãn Docling ở cột đầu.
# Giữ vì: một chuỗi dòng nối tiếp nằm giữa hai dòng hàng được cắt tại khoảng cách dọc lớn nhất (khoảng cách giữa hai hàng lớn hơn khoảng cách giữa hai dòng cùng ô);
#   phần trước thuộc dòng hàng bên trên (chữ căn đầu ô: AES "Landfill" / "Gas"), phần sau thuộc dòng hàng bên dưới (chữ căn giữa hoặc căn đáy: AMCOR p79, AMD p51).
#   Hai khoảng cách chênh dưới BOUNDARY_MARGIN thì cả chuỗi thuộc dòng bên trên; chuỗi ở đầu bảng thuộc dòng bên dưới, ở cuối bảng thuộc dòng bên trên.
#   Chữ ở cột nhãn đầu của dòng nối tiếp phải có bằng chứng: ô nhãn Docling với đúng chữ ghép của hàng và dòng nối tiếp ("funding spread risk" nối "Fair value option
#   elected liabilities -", JPM p140), không thì dòng đó có thể là một hàng chữ riêng (hàng tiêu đề lặp "December 31, 2021 (in millions)", JPM p209): bỏ cả bảng (`lines`).
#   Các dòng nối tiếp liền nhau mà chữ ghép lại đúng bằng một hàng của Docling (`docling_rows`: chữ-số đã sắp của từng hàng thân) là hàng riêng, không gắn vào hàng kề: ô header
#   hai dòng "Plan to Date" / "through 12/31/2022" của PepsiCo p79.
# Giới hạn: bảng toàn dòng nối tiếp không dựng lại (`lines`).
def attach_continuations(raw: list, known: dict, docling_rows: list = ()) -> list:
    cont = [line[3] for line in raw]
    forced: dict = {}
    i = 0
    while i < len(raw):
        if not cont[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(cont) and cont[j + 1]:
            j += 1
        span = next(((a, a + size - 1) for size in range(j - i + 1, 1, -1) for a in range(i, j - size + 2)
                     if sorted("".join(raw[k][4] for k in range(a, a + size))) in docling_rows), None)
        if span:
            for k in range(span[0], span[1] + 1):
                cont[k] = False
                forced[k] = span[0]
        i = j + 1
    root = lambda k: forced.get(k, k)
    owner = [root(k) for k in range(len(raw))]
    i = 0
    while i < len(raw):
        if not cont[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(raw) and cont[j + 1]:
            j += 1
        if i == 0 and j + 1 == len(raw):
            raise RegridSkip("lines")
        if i == 0:
            split = 0
        elif j + 1 == len(raw):
            split = j + 1
        else:
            gaps = [raw[k][2] - raw[k - 1][2] for k in range(i, j + 2)]
            ranked = sorted(gaps, reverse=True)
            split = i + gaps.index(ranked[0]) if ranked[0] - ranked[1] >= BOUNDARY_MARGIN else j + 1
        for k in range(i, j + 1):
            owner[k] = root(i - 1) if k < split else root(j + 1)
        i = j + 1
    lines = []
    for anchor in sorted(set(owner)):
        members = [raw[k] for k in range(len(raw)) if owner[k] == anchor]
        labels = [" ".join(filter(None, parts)) for parts in zip(*(member[0] for member in members))]
        if sum(bool(member[0][0]) for member in members) > 1 and adopt_label(known, labels[0]) not in known.values():
            raise RegridSkip("lines")
        lines.append((labels, [member[1] for member in members], min(member[2] for member in members), max(member[2] for member in members)))
    return lines
