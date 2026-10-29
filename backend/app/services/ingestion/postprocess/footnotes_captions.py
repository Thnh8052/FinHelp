from collections import Counter
import fitz  # PyMuPDF

from app.services.ingestion.postprocess.constants import CAPTION_MAX_WORDS, FOOTNOTE_SYMBOLS, HEADER_SEPARATOR, LEADING_PUNCT, PROSE_MIN_WORDS, PROSE_SIZE_MARGIN, TITLE_WORDS, TRAILING_PUNCT, VALUE_LINE_TOLERANCE
from app.services.ingestion.postprocess.evidence import normalise
from app.services.ingestion.postprocess.grids import Grid, row_cells, table_blocks
from app.services.ingestion.postprocess.table_values import first_value_column, is_numeric_table
from app.services.ingestion.postprocess.table_regrid import render_table
from app.services.ingestion.postprocess.table_continued import is_data_row, matched_blocks
from app.services.ingestion.postprocess.headings import heading_style, span_style, title_level


# Ý nghĩa: lỗi 17. Ký hiệu chú thích mở đầu một đoạn chữ: "(a)", "(12)", "(iii)" (trong ngoặc tối đa 2 chữ số hoặc 3 chữ cái), chuỗi toàn "*", một ký hiệu của FOOTNOTE_SYMBOLS hoặc một chữ số đứng riêng
#   ("1 Pre-tax pre-provision income means ..."); "" khi đoạn không mở đầu bằng ký hiệu, hoặc chỉ có mình ký hiệu.
# Giữ vì: "(702) 693-8711" (3 chữ số) và "(4)Instruments" (dính chữ) không phải chú thích; ký hiệu đứng một mình ("(b)" của JPM 2021Q1 p160) là ký hiệu lạc, không có đoạn chữ để lấy ra.
def footnote_marker(text: str) -> str:
    words = text.split()
    if len(words) < 2:
        return ""
    token = words[0]
    inner = token[1:-1] if token.startswith("(") and token.endswith(")") else ""
    marked = ((inner.isdigit() and len(inner) <= 2) or (inner.isalpha() and len(inner) <= 3) or set(token) <= {"*"}
              or token in FOOTNOTE_SYMBOLS or (len(token) == 1 and token.isdigit()))
    return token if marked else ""


# Ý nghĩa: lỗi 17. Chữ các hàng của lưới Docling mà MỘT ô gộp phủ cả chiều ngang (mọi ô lưới cùng chữ, cùng ô gốc ở cột 0) và là đoạn chú thích (`footnote_marker`).
def footnote_rows(grid) -> set[str]:
    return {row[0][0] for row in grid if len(row) > 1 and footnote_marker(row[0][0]) and all(slot == row[0] for slot in row)}


# Ý nghĩa: lỗi 17. Chữ duy nhất của một hàng Markdown (mọi ô có chữ cùng một chữ: ô gộp chưa bỏ bản sao cũng tính); "" khi hàng trống hoặc có từ hai chữ khác nhau.
def lone_text(row: list[str]) -> str:
    texts = {cell for cell in row if cell}
    return texts.pop() if len(texts) == 1 else ""


# Ý nghĩa: lỗi 17. Ký hiệu chú thích `marker` có được một ô nhắc đến không: là một từ riêng của ô; ký hiệu "*" và FOOTNOTE_SYMBOLS còn được dính cuối từ ("income*" của JPM p61); "(a)" dính chữ ("cost(a)") thì không.
def refers_to(marker: str, cell: str) -> bool:
    symbol = set(marker) <= {"*"} or marker in FOOTNOTE_SYMBOLS
    return any(word == marker or (symbol and word.endswith(marker)) for word in cell.split())


# Ý nghĩa: lỗi 17. Kiểu chữ PDF của các hàng một chuỗi chữ của bảng `grid` trên trang PDF `page` (số trang `number`): ({chữ: (kiểu chữ của chữ đầu, tỉ lệ chữ đậm)}, cỡ chữ điển hình của mọi ô còn lại, tính theo số ký tự);
#   ({}, None) khi bảng không có hộp bao ô hoặc không có trên trang.
# Giữ vì: cỡ chữ là bằng chứng duy nhất tách chữ thân bị nuốt vào bảng khỏi nhãn thật của bảng (xem PROSE_MIN_WORDS); gom chữ PDF của cả bảng một lần rồi gán vào ô theo tâm, thay vì mỗi ô một lần đọc PDF.
def lone_styles(page, grid: Grid, number: int, texts: set):
    if not grid.cells or number not in grid.extent:
        return {}, None
    left, top, right, bottom = grid.extent[number]
    spans = [span for block in page.get_text("dict", clip=fitz.Rect(left - 2, top - 2, right + 2, bottom + 2))["blocks"] for line in block.get("lines", [])
             for span in line["spans"] if span["text"].strip()]
    styles: dict = {}
    sizes: Counter = Counter()
    for cell in grid.cells:
        inside = [span for span in spans if cell.l - 1 <= (span["bbox"][0] + span["bbox"][2]) / 2 <= cell.r + 1 and cell.t - 1 <= (span["bbox"][1] + span["bbox"][3]) / 2 <= cell.b + 1]
        if cell.text not in texts:
            for span in inside:
                sizes[round(span["size"] * 2) / 2] += len(span["text"].strip())
        elif inside and cell.text not in styles:
            total = sum(len(span["text"].strip()) for span in inside)
            bold = sum(len(span["text"].strip()) for span in inside if span["flags"] & 16 or "bold" in span["font"].lower())
            styles[cell.text] = (span_style(inside[0]), bold / total)
    return styles, (sizes.most_common(1)[0][0] if sizes else None)


# Ý nghĩa: lỗi 17. Với mỗi khối bảng của trang đã sửa (`text`; `source` = Markdown gốc để ghép lưới Docling) lấy ra khỏi bảng các hàng chỉ có MỘT chuỗi chữ mà không phải hàng bảng:
#   (a) đoạn chú thích: mở đầu bằng ký hiệu chú thích (`footnote_marker`) mà một ô phía trên trong cùng bảng nhắc đến (`refers_to`; header hoặc hàng thân, không tính các hàng mở đầu bằng ký hiệu), và hoặc là
#       ô gộp phủ cả chiều ngang của lưới Docling (`footnote_rows`), hoặc là hàng cuối bảng, hoặc bảng là bảng số liệu;
#   (b) chữ thân bị nuốt vào bảng (cần `page` PDF): đoạn văn (PROSE_MIN_WORDS từ, không đậm, cỡ chữ lớn hơn cỡ bảng PROSE_SIZE_MARGIN điểm, sau một hàng có giá trị) và tiêu đề đậm đứng ngay trước đoạn đó.
#   Mỗi hàng thành một đoạn văn (tiêu đề thành "#" * (cấp + 1) với cấp theo kiểu chữ trong `levels` như lỗi 23; không có `levels` thì chữ thường). Hàng ở giữa bảng chia bảng làm hai: đoạn văn đứng giữa, phần sau thành bảng
#   mới (hàng đầu của nó là header; nếu là hàng dữ liệu thì thêm header trống như `carry_header`); hàng ở cuối bảng chỉ bị bỏ khỏi bảng. Bảng bị đụng được dựng lại bằng `render_table`.
#   Đếm vào `counts`: moved (hàng lấy ra), prose (trong đó chữ thân và tiêu đề), tables_split (bảng mới tạo ra), headerless, skip_ragged (hàng khác số cột), skip_blocks (số khối không khớp số khối gốc), skip_text (lưới có hàng
#   chú thích gộp mà Markdown không có hàng đó), skip_marker (không ô nào phía trên nhắc đến ký hiệu), skip_position (có ký hiệu nhưng hàng giữa bảng chữ).
# Giữ vì: hàng chú thích 711 chữ lặp 12 cột làm mọi hàng của bảng đệm tới 8,5 nghìn ký tự (JPM p242 223 KB, GM p86 chú thích "(a)" lẫn giữa các bảng con); ký hiệu có mặt trong bảng là bằng chứng nó là chú thích
#   của bảng này chứ không phải mục "(4) Instruments ..." của bảng mục lục exhibit; hàng giữa bảng chữ thì có thể là một khối ký tên ("* By: /s/ ..." rồi tên và chức danh ở các hàng sau, Verizon p112) nên không tách.
# Giới hạn: một ô có nhiều chú thích ("(a) ... (b) ...") thành một đoạn văn; chữ thân cùng cỡ chữ với bảng không nhận ra được; chạy SAU `carry_header` vì bước đó ghép khối bảng theo chỉ số.
def move_footnotes(text: str, source: str, grids: list, counts: Counter, page=None, number: int = 0, levels=None) -> str:
    lines = text.split("\n")
    matched = matched_blocks(source, grids)
    blocks = table_blocks(lines)
    if len(matched) != len(blocks):
        counts["skip_blocks"] += 1
        return text
    for k in reversed(range(len(blocks))):
        grid = matched[k][1]
        rows = [row_cells(lines[i]) for i in blocks[k]]
        if grid is None or len(rows) < 3:
            continue
        if len({len(row) for row in rows}) != 1:
            counts["skip_ragged"] += 1
            continue
        body = rows[2:]
        lone = [lone_text(row) for row in body]
        merged = footnote_rows(grid)
        marked = [j for j, chunk in enumerate(lone) if footnote_marker(chunk)]
        if merged and not any(chunk in merged for chunk in lone):
            counts["skip_text"] += 1
        extract: dict[int, str] = {}
        if marked:
            valued = [[(cell, col) for col, cell in enumerate(row)] for row, chunk in zip(body, lone) if not chunk]
            first = first_value_column(valued, len(rows[0])) if valued else None
            numeric = first is not None and is_numeric_table(valued, first, len(rows[0]))
            for j in marked:
                above = [rows[0]] + [row for i, row in enumerate(body[:j]) if i not in marked]
                if not any(refers_to(footnote_marker(lone[j]), cell) for row in above for cell in row):
                    counts["skip_marker"] += 1
                elif lone[j] in merged or numeric or j == len(body) - 1:
                    extract[j] = lone[j].replace("&#124;", "|")
                else:
                    counts["skip_position"] += 1
        long = [j for j, chunk in enumerate(lone) if len(chunk.split()) >= PROSE_MIN_WORDS and any(any(row[1:]) for row in body[:j])]
        if long and page is not None:
            styles, typical = lone_styles(page, grid, number, {chunk for chunk in lone if chunk})
            big = lambda chunk: typical is not None and chunk in styles and styles[chunk][0][0] >= typical + PROSE_SIZE_MARGIN
            prose = [j for j in long if big(lone[j]) and styles[lone[j]][1] < 0.5]
            for j in range(len(lone)):
                if j in extract:
                    continue
                if j in prose:
                    extract[j] = lone[j].replace("&#124;", "|")
                    counts["prose"] += 1
                elif j + 1 in prose and lone[j] and big(lone[j]) and styles[lone[j]][1] >= 0.5:
                    kind = (styles[lone[j]][0][0], True, styles[lone[j]][0][2])
                    extract[j] = ("#" * min(title_level(kind, levels) + 1, 6) + " " if levels is not None else "") + lone[j].replace("&#124;", "|")
                    counts["prose"] += 1
        if not extract:
            continue
        pieces: list = []
        previous = 0
        for index, j in enumerate(sorted(extract) + [len(body)]):
            part = body[previous:j]
            if index == 0:
                pieces.append([rows[0]] + part)
            elif part:
                if is_data_row(part[0]):
                    part = [[""] * len(rows[0])] + part
                    counts["headerless"] += 1
                pieces.append(part)
                counts["tables_split"] += 1
            if j < len(body):
                pieces.append(extract[j])
            previous = j + 1
        new: list[str] = []
        for piece in pieces:
            new += ([""] if new else []) + ([piece] if isinstance(piece, str) else render_table(piece))
        lines[blocks[k][0]:blocks[k][-1] + 1] = new
        counts["moved"] += len(extract)
    return "\n".join(lines)


# Ý nghĩa: lỗi 9. Hai ô của hàng header đầu tiên là tiêu đề báo cáo và tên công ty in cùng dòng: (tiêu đề, tên công ty) là hai `TableCell`, tên công ty None khi cả hàng chỉ có tiêu đề; None khi bảng không có hàng như vậy.
#   Hàng đó là hàng tiêu đề khi: bảng có ít nhất hai hàng header (`headers`) và ba cột; ô đầu của hàng (cột 0, không gộp) chỉ gồm tên báo cáo (có từ trong TITLE_WORDS, không quá CAPTION_MAX_WORDS từ); mọi ô
#   còn lại của hàng chỉ là MỘT ô phủ hết các cột giá trị và nằm cùng dòng PDF với tiêu đề (đỉnh hộp lệch không quá VALUE_LINE_TOLERANCE).
# Giữ vì: Docling kéo hộp bao bảng lên trùm cả dòng "Consolidated Statements of Income    Corning Incorporated and Subsidiary Companies" in trên bảng nên dòng đó thành hàng header đầu, và bộ ghi Markdown nối từng ô của hàng
#   đó vào header mỗi cột ("Corning Incorporated and Subsidiary Companies - Year ended December 31, - 2021" lặp ở cả ba cột năm; Corning p65-p68, p70-p73, 2022 p58-p61). Tên công ty phủ hết các cột giá trị không đặt tên cho cột nào;
#   ô phủ hết các cột giá trị ở hàng KHÔNG có tiêu đề ("Year ended December 31," của chính Corning, "JPMorgan Chase & Co." của JPM) là nhóm cột thật nên không bị xét.
# Giới hạn: chỉ hàng đầu của bảng và chỉ khi tiêu đề nằm ở ô đầu; bảng mà TableFormer không đánh dấu hàng đầu là header (Corning p69 và 2022 p62 "Changes in Shareholders' Equity": tiêu đề là hàng thân đầu tiên, header Markdown trống) không xét.
def caption_cells(grid, headers: int):
    cells = getattr(grid, "cells", ())
    if headers < 2 or not cells or len(grid[0]) < 3:
        return None
    row = [cell for cell in cells if cell.row == 0 and cell.text]
    title = next((cell for cell in row if cell.col == 0), None)
    if title is None or title.col_span != 1 or title.row_span != 1:
        return None
    words = title.text.split()
    if len(words) > CAPTION_MAX_WORDS or not {word.strip(LEADING_PUNCT + TRAILING_PUNCT).upper() for word in words} & TITLE_WORDS:
        return None
    rest = [cell for cell in row if cell is not title]
    if not rest:
        return title, None
    banner = rest[0]
    if banner.col == 1 and banner.col + banner.col_span == len(grid[0]) and banner.row_span == 1 and abs(banner.t - title.t) <= VALUE_LINE_TOLERANCE:
        return title, banner
    return None


# Ý nghĩa: lỗi 9. Ô header Markdown `cell` bỏ phần đầu là chữ của tiêu đề hoặc tên công ty (`captions`): ô chỉ có chữ đó thành rỗng, "<chữ> - <phần còn lại>" thành phần còn lại; ô khác giữ nguyên chữ (đã gộp khoảng trắng).
# Giữ vì: bộ ghi Markdown nối ô các hàng header của một cột bằng " - " theo thứ tự từ trên xuống (`_flatten_header_rows`), hàng tiêu đề là hàng trên cùng nên chữ của nó luôn đứng đầu ô.
def strip_captions(cell: str, captions: list[str]) -> str:
    text = " ".join(cell.split())
    for caption in captions:
        key = " ".join(caption.split())
        if text == key:
            text = ""
        elif text.startswith(key + HEADER_SEPARATOR):
            text = text[len(key) + len(HEADER_SEPARATOR):]
    return text


# Ý nghĩa: lỗi 9. Tách tiêu đề báo cáo và tên công ty (`caption_cells`) khỏi header của từng bảng trên trang Markdown `text` rồi đặt chúng thành dòng riêng ngay trên bảng: tiêu đề in đậm thành tiêu đề Markdown (cấp theo kiểu chữ PDF như
#   lỗi 5/23, `title_level`), tên công ty và tiêu đề không đậm là dòng chữ thường. Hàng đơn vị "(In millions, ...)" và các hàng header còn lại giữ nguyên. Đếm vào `counts`: captioned (bảng), lines (dòng đặt lên), present (dòng bỏ vì chữ đã có trên trang),
#   skip_blocks (số khối bảng khác số khối ghép được), skip_ragged (hàng khác số ô), skip_header (ô header không bắt đầu bằng chữ của tiêu đề/công ty như bộ ghi Markdown nối, hoặc còn sót chữ đó).
# Giữ vì: tên công ty lặp ở header mọi cột làm phình chunk bảng và lệch trọng số BM25 về phía tên công ty; tiêu đề báo cáo nằm lẫn trong ô nhãn "Consolidated Statements of Income - (In millions, ...)" nên chunk bảng không có tên báo cáo ở chỗ một
#   tiêu đề thật được nhận (cùng chỗ lỗi 23 đặt tiêu đề báo cáo mà Docling gán `page_header`). Chữ không mất: mỗi chữ bị bỏ khỏi header đều có mặt ở dòng đặt lên (hoặc đã có sẵn trên trang).
# Giới hạn: chạy SAU `fix_page` (nhận cả bảng đã dựng lại cột, miễn ô header còn nối bằng " - ") và TRƯỚC `carry_header` (bảng vắt trang kế thừa header đã sạch); bảng có ô header không theo cách nối này không đổi; tiêu đề đã có chữ ở nơi khác trên trang (tiêu đề Docling
#   nhận được, hoặc lỗi 23 vừa khôi phục) thì không đặt lần nữa, nhưng header vẫn được làm sạch.
def split_captions(text: str, source: str, grids: list, counts: Counter, page=None, levels=None) -> str:
    lines = text.split("\n")
    matched = matched_blocks(source, grids)
    blocks = table_blocks(lines)
    if len(matched) != len(blocks):
        counts["skip_blocks"] += 1
        return text
    plan: dict[int, list[str]] = {}
    for k in reversed(range(len(blocks))):
        length, grid = matched[k]
        found = caption_cells(grid, len(grid) - (length - 2)) if grid is not None else None
        if found is None:
            continue
        rows = [row_cells(lines[i]) for i in blocks[k]]
        if len({len(row) for row in rows}) != 1:
            counts["skip_ragged"] += 1
            continue
        title, banner = found
        names = [cell.text for cell in found if cell is not None]
        header = [strip_captions(cell, names) for cell in rows[0]]
        keys = [normalise(name) for name in names]
        if header == [" ".join(cell.split()) for cell in rows[0]] or any(key in normalise(cell) for key in keys for cell in header):
            counts["skip_header"] += 1
            continue
        lines[blocks[k][0]:blocks[k][-1] + 1] = render_table([header] + rows[2:])
        kind = heading_style(page, {"l": title.l, "t": title.t, "r": title.r, "b": title.b}) if page is not None else None
        bold = levels is not None and kind is not None and kind[1]
        plan[k] = [("#" * min(title_level(kind, levels) + 1, 6) + " " if bold else "") + " ".join(title.text.split())]
        if banner is not None:
            plan[k].append(" ".join(banner.text.split()))
        counts["captioned"] += 1
    if not plan:
        return text
    present = normalise("\n".join(lines))
    starts = [block[0] for block in table_blocks(lines)]
    for k in sorted(plan, reverse=True):
        start = starts[k]
        added = []
        for line in plan[k]:
            if normalise(line.lstrip("# ")) in present:
                counts["present"] += 1
            else:
                added += [line, ""]
        counts["lines"] += len(added) // 2
        if added:
            lines[start:start] = ([""] if start and lines[start - 1].strip() else []) + added
    return "\n".join(lines)
