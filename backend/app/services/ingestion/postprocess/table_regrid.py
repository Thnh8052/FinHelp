from collections import Counter

from app.services.ingestion.postprocess.constants import LABEL_COLUMN_TOLERANCE, PHRASE_GAP, ROW_MISMATCH, TEXT_FOLD, VALUE_GAP_TOLERANCE
from app.services.ingestion.postprocess.evidence import glue_superscripts, is_footnote_ref, normalise, sits_on
from app.services.ingestion.postprocess.grids import row_cells, table_blocks
from app.services.ingestion.postprocess.table_values import RegridSkip, attach_continuations, distance_to_column, first_value_column, group_value_words, is_numeric_table, is_span_copy, label_hosts, label_key, match_grid, phrase_cells, split_lines, value_columns, value_words, wrap_rows
from app.services.ingestion.postprocess.tokens import is_marker, is_number


# Ý nghĩa: lỗi 13. Dựng lại các hàng thân của bảng số liệu từ dòng chữ PDF khi hàng Docling không khớp chữ PDF; trả ([(nhãn theo cột nhãn, [dòng từ giá trị], trên, dưới)], {từ: số lần}
#   Docling lỡ nhét vào ô header) với từ giá trị = (x0, x1, chữ), hoặc ném RegridSkip(lý do): `labels`, `span`, `lines`, `bridge`, `mixed`, `values_changed`, `labels_changed`.
#   Vùng quét là hộp bao các ô thân của Docling; từ có tâm bên trái ô giá trị trái nhất là chữ nhãn (xếp vào cột nhãn theo mép trái ô nhãn của Docling), còn lại là giá trị;
#   chỉ số chú thích "(7)" sát chữ nhãn (cách không quá VALUE_GAP_TOLERANCE) ở lại ô nhãn, không thành cột giá trị.
# Giữ vì: TableFormer gộp hai dòng sát nhau làm một hàng ("Depreciation and amortization Loss on disposal ..." với "1,053 9"; AES p14 "Solar Wind" với "967 140"), đẩy giá
#   trị sang hàng khác (AES p135 "Other" / "liabilities:" có 120 ở hàng dưới) và xé nhãn; dòng chữ PDF thì không bao giờ sai hàng. Bảo toàn: chữ-số và ký hiệu của vùng giá
#   trị bằng chữ các ô giá trị của Docling, chữ-số của nhãn bằng chữ các ô nhãn (không từ nào thừa, vùng quét lấn ra ngoài bảng thì bỏ); chữ PDF mà Docling không có chỉ được
#   nhận khi Docling đã nhét nó vào ô header ("designated hedges 6", Corning p108; "1 3", AES p2), và số Docling đặt nhầm ở cột nhãn ("3,390", AES p39) được coi là giá trị.
#   Hàng = dòng có cụm số (phrase_cells: cụm chữ liền nhau theo PHRASE_GAP, số trong câu chữ như "December 2005." không tính); dòng không có cụm số mà có chữ ở vùng giá trị
#   hoặc cột nhãn thứ hai trở đi là chữ xuống dòng của hàng kề (attach_continuations); dòng chỉ có chữ ở cột nhãn đầu là hàng chỉ có nhãn (wrap_rows).
#   Đo trên 80 tài liệu: 186 bảng có hàng Docling không khớp PDF, 117 dựng lại; số ô có từ hai giá trị trở lên trong các bảng dựng lại 480 -> 8, số ô "bằng tổng các ô
#   trên" theo cột 888 -> 1052, không bảng nào giảm.
# Giới hạn: ô giá trị gộp (span) loại cả bảng. Hàng con (AES "Solar 967" / "Wind 140": cùng cột số hai lần) là hàng riêng với nhãn trống; ô chữ của cột khác (khách hàng
#   "Non-Profit") ở lại dòng của nó. Cụm chữ chạm cột số (PepsiCo p72) hoặc dòng chú thích bắc cầu hai cột (AMD p70) thì bỏ. Tên nằm lệch nửa dòng so với số tuổi trong danh
#   sách lãnh đạo (Adobe p16, Boeing p127) không dựng lại đúng: chỉ chạy khi hàng có số ở từ hai dòng trở lên, các bảng đó giữ nguyên Docling. Việc chia cột giá trị do `regrid_block`.
def reflow_rows(cells: tuple, headers: int, first: int, page_words: list) -> list:
    body = [c for c in cells if c.row >= headers and c.text]
    values = [c for c in body if c.col >= first]
    if not values or any(c.row_span > 1 or c.col_span > 1 for c in values):
        raise RegridSkip("span")
    starts = {col: min(c.l for c in body if c.col == col) for col in range(first) if any(c.col == col for c in body)}
    if not starts:
        raise RegridSkip("labels")
    left, right = min(c.l for c in values) - 1.5, max(c.r for c in values) + 1.5
    top, bottom, edge = min(c.t for c in body) - 1, max(c.b for c in body) + 1, min(c.l for c in body) - 2
    inside = [((y0 + y1) / 2, x0, x1, text) for x0, y0, x1, y1, text, *_ in page_words
              if edge <= (x0 + x1) / 2 <= right and top <= (y0 + y1) / 2 <= bottom]
    drawn = []
    for line in split_lines(inside):
        labels, last = [""] * first, None
        for _, x0, x1, text in line:
            if (x0 + x1) / 2 < left:
                col = max((c for c in starts if starts[c] - LABEL_COLUMN_TOLERANCE <= x0), default=min(starts))
                labels[col] = f"{labels[col]} {text.translate(TEXT_FOLD).replace('|', '&#124;')}".strip()
                last = (x1, col)
        drawn.append((labels, [word for word in line if (word[1] + word[2]) / 2 >= left], sum(word[0] for word in line) / len(line), last))
    pdf_values = Counter("".join(text for _, words, _, _ in drawn for _, _, _, text in words).translate(TEXT_FOLD))
    pdf_labels = Counter("".join(normalise(label) for labels, _, _, _ in drawn for label in labels))
    label_cells = [c for c in body if c.col < first]
    header_cells = [c for c in cells if c.row < headers and c.text]
    header_values = Counter("".join("".join(c.text.translate(TEXT_FOLD).split()) for c in header_cells))
    header_labels = Counter("".join(normalise(c.text) for c in header_cells))
    strays = [c for c in label_cells if all(is_number(token) for token in c.text.translate(TEXT_FOLD).split())]
    for moved in ([], strays):
        docling_values = Counter("".join("".join(c.text.translate(TEXT_FOLD).split()) for c in values + moved))
        docling_labels = Counter("".join(normalise(c.text) for c in label_cells if c not in moved))
        lost_values, lost_labels = pdf_values - docling_values, pdf_labels - docling_labels
        if not docling_values - pdf_values and not docling_labels - pdf_labels \
                and not lost_values - header_values and not lost_labels - header_labels:
            break
    else:
        raise RegridSkip("values_changed" if pdf_values != Counter("".join("".join(c.text.translate(TEXT_FOLD).split()) for c in values)) else "labels_changed")
    inside_tokens = Counter(word[3].translate(TEXT_FOLD) for word in inside)
    body_tokens = Counter(token for c in body for token in c.text.translate(TEXT_FOLD).split())
    header_tokens = {token for c in header_cells for token in c.text.translate(TEXT_FOLD).split()}
    moved_out = Counter({token: count for token, count in (inside_tokens - body_tokens).items() if token in header_tokens}) if lost_values or lost_labels else Counter()
    docling_rows = [sorted("".join(normalise(c.text) for c in body if c.row == row)) for row in {c.row for c in body}]
    raw = []
    for labels, words, cy, last in drawn:
        while last and words and is_marker(words[0][3]) and words[0][1] - last[0] <= VALUE_GAP_TOLERANCE:
            labels[last[1]] += " " + words[0][3].translate(TEXT_FOLD)
            last, words = (words[0][2], last[1]), words[1:]
        words = [(x0, x1, text) for _, x0, x1, text in words]
        chars = "".join(normalise(text) for text in labels + [text for _, _, text in words])
        raw.append((labels, words, cy, (bool(words) or any(labels[1:])) and not any(numeric for _, _, numeric in phrase_cells(words)) and sorted(chars) not in docling_rows, chars))
    marks = []
    for _, words, _, _, _ in raw:
        phrases = phrase_cells(words)
        for group in group_value_words(words):
            numeric = any(p0 - 0.5 <= group[0] <= p1 + 0.5 and numeric for p0, p1, numeric in phrases)
            if not numeric or any(ch.isdigit() for token in group[2] for ch in token):
                marks.append((group[0], group[1], numeric))
    if any(n[0] <= t[1] + VALUE_GAP_TOLERANCE and t[0] <= n[1] + VALUE_GAP_TOLERANCE
           for n in value_columns([m for m in marks if m[2]]) for t in value_columns([m for m in marks if not m[2]])):
        raise RegridSkip("mixed")
    row_columns = value_columns([group for _, words, _, cont, _ in raw if not cont for group in group_value_words(words)], PHRASE_GAP)
    if any(sum(row[0] >= column[0] and row[1] <= column[1] for row in row_columns) > 1
           for column in value_columns([group for _, words, _, _, _ in raw for group in group_value_words(words)], PHRASE_GAP)):
        raise RegridSkip("bridge")
    known = [{label_key(c.text): c.text for c in body if c.col == col} for col in range(first)]
    rows = wrap_rows(attach_continuations(raw, known[0], docling_rows), known)
    spans = [c for c in label_cells if c.row_span > 1]
    bands: dict = {}
    for c in body:
        bands[c.row] = (min(c.t, bands.get(c.row, (c.t, c.b))[0]), max(c.b, bands.get(c.row, (c.t, c.b))[1]))
    for labels, _, top, bottom in rows:
        grid_row = next((row for row, (lo, hi) in bands.items() if lo - 1 <= (top + bottom) / 2 <= hi + 1), None)
        for span in spans:
            if grid_row is not None and not labels[span.col] and span.row < grid_row < span.row + span.row_span:
                labels[span.col] = span.text
    return rows, moved_out


# Ý nghĩa: các hàng thân của bảng cho `regrid_block`: [(các ô nhãn, [(x0, x1, từ)])], cờ "hàng dựng lại từ dòng chữ PDF" và {từ: số lần} Docling lỡ nhét vào ô header. Hàng của Docling khi
#   chữ PDF khớp từng hàng (value_words); khi giá trị nằm sai hàng hoặc một hàng gộp hai dòng (ROW_MISMATCH) thì dựng lại từ dòng chữ PDF (lỗi 13), các từ
#   giá trị của hàng theo thứ tự đọc (dòng trên trước, trái sang phải); dựng lại không được thì giữ lý do bỏ qua cũ và đếm `reflow_skip_<lý do>`.
def body_rows(rows: list, grid, headers: int, first: int, page_words: list, counts: Counter):
    try:
        by_row = value_words(grid.cells, headers, first, page_words)
    except RegridSkip as skip:
        if skip.reason not in ROW_MISMATCH:
            raise
        try:
            rebuilt, moved_out = reflow_rows(grid.cells, headers, first, page_words)
            return [(labels, [group for words in lines for group in group_value_words(words)]) for labels, lines, *_ in rebuilt], True, moved_out
        except RegridSkip as declined:
            counts[f"reflow_skip_{declined.reason}"] += 1
            raise skip from None
    labels = lambda k, row: ["" if is_span_copy([grid[row]], col) else rows[2 + k][col] for col in range(first)]
    return [(labels(k, row), group_value_words(by_row.get(row, []))) for k, row in enumerate(range(headers, len(grid)))], False, Counter()


# Ý nghĩa: các cụm giá trị chỉ chứa chỉ số chú thích ("(i)", "(f)(g)") thay cho giá trị: tập chỉ số trong `columns`. `groups`: các giá trị (x0, x1, [từ]) của mọi hàng.
def marker_columns(columns: list, groups: list) -> set:
    flags: dict = {}
    for x0, x1, tokens in groups:
        flags.setdefault(next(i for i, column in enumerate(columns) if column[0] <= x0 and x1 <= column[1]), []).append(is_marker("".join(tokens)))
    return {index for index, found in flags.items() if all(found)}


# Ý nghĩa: lỗi 16. Các cột "ma" của lưới Docling: cột (từ sau cột giá trị đầu tiên) mà mọi ô thân có chữ chỉ là chỉ số chú thích, mỗi chỉ số in nhỏ đứng sau một từ của ô kề trái (`sits_on`) và
#   chữ các chỉ số ghép lại đúng bằng chữ ô; cột kề trái không phải cột ma; header của cột trống, hoặc các thành phần của nó (cách nhau " - ") đã nằm liền nhau trong header của MỘT cột không phải cột chỉ số (`header`: hàng header Markdown).
# Giữ vì: chỉ số in nhỏ được Docling đặt vào cột riêng ("(43)" | "(a)", "1%" | "3"): cột đó không có số liệu của riêng nó, mọi ô của nó thuộc ô bên trái. Bằng chứng là cỡ chữ và vị trí PDF chứ không
#   phải hình dạng chữ: cột "Age", "Page" toàn số 1-2 chữ số hoặc cột "(1)" "(2)" của số âm không phải chú thích. Xét theo ô Docling kề trái (không theo khoảng cách) vì chỉ số căn trái ở vị trí cố định
#   cách xa nhãn chữ ngắn ("Consumer & Business Banking" rồi "(d)", JPM 2021Q1 p21). Header phải trống hoặc đã có ở cột khác ("Percent Change - 2016 versus 2015" nằm trong tên hai cột kề) để bỏ cột không mất tên nào; các thành phần rải ở nhiều header không tính ("Six months ended June 30, - 2022 - Total changes ..."
#   của JPM 2022Q2 p110 có đủ thành phần ở hai khối năm nhưng riêng tổ hợp 2022 chỉ có ở cột này);
#   header là chính ký hiệu ("*" của Boeing 2018 p28: "737 *" và các số nhỏ "(18)" bên dưới là số giao nội bộ của cột đó, không phải chú thích) không có ở cột nào khác nên cột đó giữ nguyên.
# Giới hạn: header của cột ma chứa một mảnh tên cột khác ("2021 - other income" của "All other income" bị xé, JPM p191) thì cột ma không bị gộp; hai cột ma liền nhau không gộp cột nào ngoài cột đầu.
def ghost_columns(cells: tuple, headers: int, first: int, ncols: int, page_words: list, header: list) -> list:
    refs = [word for word in page_words if is_footnote_ref(word[4].translate(TEXT_FOLD))]
    if not headers or not refs:
        return []
    body = [c for c in cells if c.row >= headers and c.text]
    inside = lambda c, words: [w for w in words if c.l - 1 <= (w[0] + w[2]) / 2 <= c.r + 1 and c.t - 1 <= (w[1] + w[3]) / 2 <= c.b + 1]

    def written(c):
        host = next((h for h in body if h.row == c.row and h.col <= c.col - 1 < h.col + h.col_span), None)
        hosts = inside(host, page_words) if host is not None else []
        return "".join(w[4] for w in sorted(inside(c, refs)) if any(sits_on(w, h) for h in hosts)).translate(TEXT_FOLD) if hosts else None

    only_markers = []
    for col in range(first + 1, ncols):
        column = [c for c in body if c.col == col]
        if column and not any(c.col_span > 1 or c.row_span > 1 for c in column) and all(written(c) == "".join(c.text.translate(TEXT_FOLD).split()) for c in column):
            only_markers.append(col)
    parts = lambda col: header[col].split(" - ") if header[col] else []
    contains = lambda small, big: any(big[i:i + len(small)] == small for i in range(len(big) - len(small) + 1))
    named = lambda col: not parts(col) or any(contains(parts(col), parts(k)) for k in range(ncols) if k not in only_markers)
    return [col for col in only_markers if col - 1 not in only_markers and named(col)]


# Ý nghĩa: lỗi 16. Bảng `table` ([header, hàng thân ...], mỗi hàng là danh sách ô) bỏ các cột ma `ghosts`: chữ của ô cột ma nối vào ô kề trái (cách một dấu cách). Header của cột ma chỉ bị bỏ, trừ khi header của cột kề phải
#   đang trống: ô header gộp bắt đầu ở cột ma và `unspan_tables` đã xóa bản sao của nó ở cột số (JPM 2021Q1 p44 "Average - 2020"), nên nhãn chuyển sang cột kề phải.
def merge_ghost_columns(table: list, ghosts: list) -> list:
    merged = [list(row) for row in table]
    for col in ghosts:
        for row in merged[1:]:
            row[col - 1] = f"{row[col - 1]} {row[col]}".strip()
        if col + 1 < len(merged[0]) and merged[0][col] and not merged[0][col + 1] and col + 1 not in ghosts:
            merged[0][col + 1] = merged[0][col]
    return [[cell for col, cell in enumerate(row) if col not in ghosts] for row in merged]


# Ý nghĩa: bỏ khỏi chữ một ô header các từ Docling lỡ nhét vào ô header nhưng PDF đặt ở thân bảng (`moved_out`: {từ: số lần}, mỗi từ chỉ bỏ số lần còn lại).
# Giữ vì: Docling kéo giá trị ngay dưới header vào ô header ("designated hedges 6", Corning p108; "1 3", AES p2); thân bảng dựng lại đã có từ đó nên header không được giữ thêm.
def strip_moved(cell: str, moved_out: Counter) -> str:
    kept = []
    for token in cell.split():
        if moved_out[token.translate(TEXT_FOLD)] > 0:
            moved_out[token.translate(TEXT_FOLD)] -= 1
        else:
            kept.append(token)
    return " ".join(kept) if len(kept) != len(cell.split()) else cell


# Ý nghĩa: ghép nối tên cột: các tên (chữ gộp qua dòng header của Docling, nối bằng " - ") của nhiều nhãn lá về một cụm giá trị thành một tên, mỗi thành phần chỉ một lần.
def join_names(names: list) -> str:
    parts: list = []
    for name in names:
        parts += [part for part in name.split(" - ") if part not in parts]
    return " - ".join(parts)


# Ý nghĩa: lỗi 13b. Tên cho từng cụm giá trị khi ghép chặt nhãn lá - cụm (mỗi nhãn một cụm riêng, theo thứ tự, tâm nhãn nằm trong cụm) không được, vì header Docling
#   sai số cột. Ba nới lỏng, mỗi nhãn lá xét trên các cụm số (không tính cụm chỉ có chỉ số chú thích): (1) tâm nhãn không nằm trong cụm vẫn được nếu cụm gần nhất cách không quá
#   VALUE_GAP_TOLERANCE và gần hơn cụm thứ nhì ít nhất 2 * VALUE_GAP_TOLERANCE (JPM p295 "Rate" lệch 2,6 điểm); (2) nhiều nhãn lá về cùng một cụm (Docling xé "Criticized" / "nonperforming" thành hai cột xếp chồng, JPM p121) thì nối tên, chỉ khi hộp các nhãn chồng nhau theo chiều ngang (ba nhãn đứng cạnh nhau
#   trên một cụm là cụm bị gộp quá tay: Coca-Cola p109 "$ 263 $ 19 $ 282" liền nhau); (3) chữ trong hộp
#   một nhãn lá rơi vào từ hai cụm số trở lên (Docling gộp "Settlements (h)" và "Transfers into level 3" làm một ô, JPM p183) thì tách theo cụm, với điều kiện các mảnh ghép lại
#   đúng bằng chữ của ô; hộp nhãn chứa trọn hai cụm số mà không tách được thì bỏ. Trả danh sách tên theo cụm hoặc ném RegridSkip("columns").
# Giữ vì: chỉ thử sau khi ghép chặt thất bại nên bảng đã dựng lại đúng không đổi; thứ tự cụm của các nhãn lá không giảm, cụm không nhãn để trống tên.
# Giới hạn: tên của nhãn lá vẫn là chữ Docling gộp nên thành phần nhóm của header có thể sai ("Selected metrics" ở cột "Criticized nonperforming", JPM p121); nhãn nằm giữa hai
#   cụm số (cách nhau chưa đủ ngưỡng) hoặc mảnh tách không ghép lại đúng thì bỏ.
def relaxed_names(rows: list, cells: tuple, headers: int, leaves: list, columns: list, markers: set, page_words: list) -> list:
    real = [j for j in range(len(columns)) if j not in markers]
    if not real:
        raise RegridSkip("columns")
    parts: dict = {}
    reached = 0
    for leaf in leaves:
        labels = [c for c in cells if c.row < headers and c.col == leaf and c.text]
        if not labels:
            raise RegridSkip("columns")
        label = min(labels, key=lambda c: (c.col_span, -c.row))
        inside = [((y0 + y1) / 2, x0, x1, word) for x0, y0, x1, y1, word, *_ in page_words
                  if label.l - 1 <= (x0 + x1) / 2 <= label.r + 1 and label.t - 1 <= (y0 + y1) / 2 <= label.b + 1]
        nearest = lambda x: min(real, key=lambda j: distance_to_column(x, columns[j]))
        ordered = [word for line in split_lines(inside) for word in line]
        owners = [nearest((x0 + x1) / 2) for _, x0, x1, _ in ordered]
        if len(set(owners)) > 1:
            pieces = {j: " ".join(word for (_, _, _, word), owner in zip(ordered, owners) if owner == j) for j in sorted(set(owners))}
            if sorted("".join(pieces.values()).translate(TEXT_FOLD).replace(" ", "")) != sorted("".join(label.text.translate(TEXT_FOLD).split())):
                raise RegridSkip("columns")
            chosen = {j: rows[0][leaf].replace(label.text, piece) if label.text in rows[0][leaf] else piece for j, piece in pieces.items()}
        else:
            centre = (label.l + label.r) / 2
            ranked = sorted(real, key=lambda j: distance_to_column(centre, columns[j]))
            nearest_gap = distance_to_column(centre, columns[ranked[0]])
            over_marker = any(distance_to_column(centre, columns[j]) == 0 for j in markers)
            ambiguous = nearest_gap and len(ranked) > 1 and distance_to_column(centre, columns[ranked[1]]) - nearest_gap < 2 * VALUE_GAP_TOLERANCE
            if not over_marker and (nearest_gap > VALUE_GAP_TOLERANCE or ambiguous or sum(label.l - 1 <= columns[j][0] and columns[j][1] <= label.r + 1 for j in real) > 1):
                raise RegridSkip("columns")
            chosen = {ranked[0]: rows[0][leaf]}
        if min(chosen) < reached:
            raise RegridSkip("columns")
        reached = max(chosen)
        for j, name in chosen.items():
            parts.setdefault(j, []).append((leaf, name, label))
    names = []
    for j in range(len(columns)):
        found = parts.get(j, [])
        if len(found) > 1:
            if any(min(a.r, b.r) - max(a.l, b.l) < 0.5 * min(a.r - a.l, b.r - b.l) for (_, _, a), (_, _, b) in zip(found, found[1:])):
                raise RegridSkip("columns")
            kept = []
            for leaf, name, _ in found:
                outside = {c.text for c in cells if c.row < headers and c.col_span > 1 and c.col <= leaf < c.col + c.col_span
                           and (c.r < columns[j][0] - 1 or c.l > columns[j][1] + 1)}
                kept.append(" - ".join(part for part in name.split(" - ") if part not in outside))
            names.append(join_names(kept))
        else:
            names.append(found[0][1] if found else "")
    return names


# Ý nghĩa: các dòng Markdown của một bảng (`table`: hàng đầu là header, mỗi hàng là danh sách ô cùng số cột): mỗi cột đệm đến ô dài nhất của nó như bộ ghi của Docling.
def render_table(table: list) -> list[str]:
    widths = [max(len(line[col]) for line in table) for col in range(len(table[0]))]
    render = lambda line: "| " + " | ".join(cell.ljust(width) for cell, width in zip(line, widths)) + " |"
    return [render(table[0]), "|" + "|".join("-" * (width + 2) for width in widths) + "|"] + [render(line) for line in table[1:]]


# Ý nghĩa: lỗi 12. Dựng lại các cột giá trị của một bảng số liệu từ vị trí chữ trong PDF; trả các dòng Markdown mới (cùng số dòng với khối cũ,
#   trừ bảng có hàng dựng lại từ dòng chữ PDF: lỗi 13, `body_rows`) hoặc None khi không áp dụng, bảng đã đúng, hoặc bị loại (đếm lý do vào
#   `counts`: regridded, reflowed, regrid_same, regrid_skip_<lý do>, reflow_skip_<lý do>).
# Giữ vì: TableFormer chia cột theo khoảng trắng nên "$" của năm sau dính vào số của năm trước ("(13) $" | "148", Corning p76), số của hàng
#   thưa (217) nằm lệch cột so với header, "$" và "%" thành cột riêng. Vị trí chữ trong PDF cho biết giá trị nào thuộc cột nào: "$" dính vào số
#   nó đứng trước, các giá trị gom thành cột theo khoảng ngang (value_columns), mỗi nhãn header (cột không phải bản sao ô gộp) ghép vào cột
#   gần tâm nhãn nhất. Trên 632 bảng số liệu không có dấu hiệu lỗi, kết quả giống hệt bảng của Docling (kiểm chứng phương pháp).
# Giới hạn: các nhãn phải ghép vào các cột khác nhau theo đúng thứ tự trái sang phải; cột còn thừa (chỉ số chú thích "(1)") để trống nhãn, và khi
#   có cột thừa thì tâm mỗi nhãn phải nằm trong cột của nó (nhãn nằm giữa số và chỉ số chú thích thì không biết thuộc cột nào). Chữ phải khớp
#   từng hàng (value_words); hàng bị Docling gộp hai dòng hoặc giá trị sai hàng thì dựng lại hàng từ dòng chữ PDF (lỗi 13) nếu bảng số thuần,
#   không được thì bị loại. Ô gộp trong thân bị loại; header sai số cột chỉ được sửa (relaxed_names, lỗi 13b) ở bảng đã dựng lại hàng, còn lại bị loại (`regrid_skip_columns`).
#   Với bảng dựng lại hàng, ô giá trị chữ lấy đúng chữ ô Docling cùng khóa (label_key), từ Docling nhét vào header được bỏ khỏi header (strip_moved).
def regrid_block(rows: list, grid, headers: int, page_words: list, counts: Counter, ghosts: list = ()):
    cells = getattr(grid, "cells", ())
    ncols = len(grid[0])
    first = first_value_column(grid[headers:], ncols)
    if not cells or not page_words or not headers or first is None or not is_numeric_table(grid[headers:], first, ncols):
        return None
    try:
        body, reflowed, moved_out = body_rows(rows, grid, headers, first, page_words, counts)
        groups = [group for _, row_groups in body for group in row_groups]
        columns = value_columns(groups)
        header = grid[:headers]
        copies = [col for col in range(ncols) if is_span_copy(header, col)]
        leaves = [col for col in range(first, ncols) if col not in copies and (col not in ghosts or col + 1 in copies) and any(row[col][0] for row in header)]
        centres = []
        for leaf in leaves:
            labels = [c for c in cells if c.row < headers and c.col == leaf and c.text]
            if not labels:
                raise RegridSkip("columns")
            label = min(labels, key=lambda c: (c.col_span, -c.row))
            centres.append((label.l + label.r) / 2)
        if ghosts and len(columns) > len(leaves):
            raise RegridSkip("ghost")
        assigned = [min(range(len(columns)), key=lambda j: distance_to_column(centre, columns[j])) for centre in centres]
        spare = len(columns) > len(leaves)
        names = [""] * len(columns)
        if leaves and assigned == sorted(set(assigned)) and not (spare and any(distance_to_column(c, columns[j]) for c, j in zip(centres, assigned))):
            for leaf, index in zip(leaves, assigned):
                names[index] = rows[0][leaf]
        elif reflowed:
            names = relaxed_names(rows, cells, headers, leaves, columns, marker_columns(columns, groups), page_words)
        else:
            raise RegridSkip("columns")
    except RegridSkip as skip:
        counts[f"regrid_skip_{skip.reason}"] += 1
        return None
    spellings: dict = {}
    for c in cells:
        if c.text:
            spellings.setdefault(label_key(c.text), set()).add(c.text)
    spelling = {key: next(iter(found)) for key, found in spellings.items() if len(found) == 1} if reflowed else {}
    table = [["" if col in copies else rows[0][col] for col in range(first)] + names]
    table[0] = [strip_moved(cell, moved_out) for cell in table[0]]
    for row_labels, row_groups in body:
        values = [""] * len(columns)
        for x0, x1, tokens in row_groups:
            index = next(i for i, column in enumerate(columns) if column[0] <= x0 and x1 <= column[1])
            values[index] = f"{values[index]} {' '.join(tokens)}".strip()
        table.append(row_labels + [spelling.get(label_key(value), value) for value in values])
    if table == [rows[0]] + rows[2:]:
        counts["regrid_same"] += 1
        return None
    counts["reflowed" if reflowed else "regridded"] += 1
    counts["ghosts_merged"] += len(ghosts)
    return render_table(table)


# Ý nghĩa: lỗi 3. Với mỗi khối bảng Markdown của trang: ghép với bảng Docling, xóa chữ ở các ô bản sao của ô gộp ngang (thay bằng đúng
#   ngần ấy dấu cách để bảng giữ nguyên căn cột). Lỗi 11: ở header, nhãn của cột "$" được chuyển sang cột số kề phải (`label_hosts`) thay vì
#   bị bỏ ở cột số. Lỗi 12: bảng số liệu có chữ PDF (`page_words`) và hộp bao ô được dựng lại cột (`regrid_block`) trước, bảng đã dựng lại không
#   qua hai bước kia. Lỗi 13: hàng dựng lại từ dòng chữ PDF làm đổi số dòng của khối, các khối sau được dịch theo. Đếm vào `counts`: blocks,
#   matched, unmatched, tables_changed, cells_blanked, labels_moved, regridded, reflowed, regrid_same, regrid_skip_* (kể cả `wrapped`: chữ xuống dòng), reflow_skip_*.
# Giữ vì: "Consolidated Statements of Income" lặp 3 lần trên một hàng làm phình token chunk bảng và lệch trọng số BM25 về phía nhãn.
# Giới hạn: chạy TRƯỚC mọi bước sửa chữ khác (cần chữ ô còn nguyên văn để so khớp). Ô gộp theo hàng không xử lý. Khối không ghép được
#   thì giữ nguyên, không đoán.
def unspan_tables(text: str, grids: list, counts: Counter, page_words: list = ()) -> str:
    lines = text.split("\n")
    candidates = list(grids)
    glued = glue_superscripts(page_words)
    shift = 0
    for block in table_blocks(lines):
        block = [i + shift for i in block]
        counts["blocks"] += 1
        rows = [[cell.strip() for cell in lines[i].strip().strip("|").split("|")] for i in block]
        grid = match_grid(rows, candidates)
        if grid is None:
            counts["unmatched"] += 1
            continue
        candidates.remove(grid)
        counts["matched"] += 1
        headers = len(grid) - (len(block) - 2)
        first = first_value_column(grid[headers:], len(grid[0]))
        ghosts = ghost_columns(getattr(grid, "cells", ()), headers, first, len(grid[0]), page_words, rows[0]) if first is not None else []
        regridded = regrid_block(rows, grid, headers, glued, counts, ghosts)
        if regridded:
            lines[block[0]:block[-1] + 1] = regridded
            shift += len(regridded) - len(block)
            continue
        groups = [(0, grid[:headers])] if headers else []
        groups += [(2 + k, [grid[headers + k]]) for k in range(len(block) - 2)]
        changed = 0
        for offset, group_rows in groups:
            copies = [col for col in range(len(grid[0])) if is_span_copy(group_rows, col)]
            if copies:
                hosts = label_hosts(grid[headers:], copies) if offset == 0 else {}
                parts = lines[block[offset]].split("|")
                for col in copies:
                    if col in hosts:
                        label = parts[hosts[col] + 1].strip()
                        parts[hosts[col] + 1] = " " * len(parts[hosts[col] + 1])
                        parts[col + 1] = " " + label.ljust(len(parts[col + 1]) - 1)
                    else:
                        parts[col + 1] = " " * len(parts[col + 1])
                lines[block[offset]] = "|".join(parts)
                changed += len(copies)
                counts["labels_moved"] += len(hosts)
        counts["cells_blanked"] += changed
        counts["tables_changed"] += bool(changed)
        if ghosts:
            current = [row_cells(lines[i]) for i in block]
            lines[block[0]:block[-1] + 1] = render_table(merge_ghost_columns([current[0]] + current[2:], ghosts))
            counts["ghosts_merged"] += len(ghosts)
    return "\n".join(lines)
