from collections import Counter
from typing import NamedTuple
import fitz  # PyMuPDF

from app.services.ingestion.postprocess.constants import BOLD_BODY_MAX, BOLD_DATA_MAX, BOLD_HEADER_MIN, CONTINUED_EDGE_TOLERANCE, CONTINUED_VERTICAL_SLACK, CONTINUED_WORD, FURNITURE_LABELS
from app.services.ingestion.postprocess.evidence import normalise
from app.services.ingestion.postprocess.grids import Grid, page_span, row_cells, table_blocks
from app.services.ingestion.postprocess.table_values import match_grid
from app.services.ingestion.postprocess.tokens import is_number


# Ý nghĩa: lỗi 14. Từ docling.json: {số trang: [(trên, dưới, nhãn, chữ đã chuẩn hóa)]} của mọi dòng chữ và hình trên trang, trừ đầu/cuối trang chạy.
# Giữ vì: hai bảng liền nhau qua trang chỉ là một bảng khi giữa chúng không còn phần tử nào của trang (xem `adjacent_tables`).
def page_items(data: dict) -> dict[int, list]:
    heights = {int(page): info["size"]["height"] for page, info in data["pages"].items()}
    by_page: dict[int, list] = {}
    for item in data["texts"] + data["pictures"]:
        if item["label"] in FURNITURE_LABELS:
            continue
        for prov in item["prov"]:
            top, bottom = page_span(prov["bbox"], heights[prov["page_no"]])
            by_page.setdefault(prov["page_no"], []).append((top, bottom, item["label"], normalise(item.get("text", ""))))
    return by_page


# Ý nghĩa: lỗi 14. Với từng khối bảng Markdown của một trang: (số dòng của khối, lưới Docling), ghép như `unspan_tables`; lưới None khi không ghép được.
def matched_blocks(text: str, grids: list) -> list[tuple[int, object]]:
    lines = text.split("\n")
    candidates = list(grids)
    matched = []
    for block in table_blocks(lines):
        grid = match_grid([row_cells(lines[i]) for i in block], candidates)
        if grid is not None:
            candidates.remove(grid)
        matched.append((len(block), grid))
    return matched


# Ý nghĩa: lỗi 14. Hàng có phải hàng dữ liệu không: ô đầu là nhãn (có chữ không phải giá trị), các ô còn lại chỉ gồm từ của giá trị (số, "$", "%", "-"),
#   có ít nhất một chữ số, và không từ nào là năm.
# Giữ vì: header của bảng tài chính có tên cột là chữ hoặc năm ("2022", "FY2022"); hàng chỉ có nhãn + số liệu thường (Virginia | 34 | 8 | -) là thân bảng.
# Giới hạn: hàng chữ thuần (danh sách công ty con, mục lục) không phân biệt được với header chỉ bằng nội dung; trường hợp đó dùng kiểu chữ (`bold_share`).
def is_data_row(row: list[str]) -> bool:
    words = [word for cell in row[1:] for word in cell.split()]
    return (not all(is_number(word) for word in row[0].split()) and bool(words) and all(is_number(word) for word in words)
            and any(ch.isdigit() for word in words for ch in word)
            and not any(word.isdigit() and len(word) == 4 and 1900 <= int(word) <= 2100 for word in words))


# Ý nghĩa: lỗi 14. Hàng có giá trị đầu tiên của bảng (các hàng `rows` từ trên xuống): bỏ qua hàng chỉ có nhãn ở ô đầu (tên mục "PHARMACEUTICAL (1)", "Immunology"
#   của J&J p82), vì hàng như vậy không phải header cột; None nếu bảng không có hàng nào có giá trị.
def content_row(rows: list[list[str]]):
    return next((row for row in rows if any(row[1:])), None)


# Ý nghĩa: lỗi 14. Header `header` dùng được cho bảng có hàng giá trị `row` không: cùng số cột, có chữ, không phải hàng dữ liệu, và có nhãn ở mọi cột mà `row` có giá trị.
# Giữ vì: header chỉ có tên nhóm ("PHARMACEUTICAL (1)" + ô trống) hoặc header trống không đặt được tên cho cột nào; chép nó sang chỉ thêm nhiễu.
def usable_header(header: list[str], row: list[str]) -> bool:
    return len(header) == len(row) and any(header) and not is_data_row(header) and all(header[col] for col, cell in enumerate(row) if col and cell)


# Ý nghĩa: lỗi 14. Tỉ lệ chữ in đậm (theo số ký tự) của các hàng lưới `rows` của bảng `grid` trên trang PDF `page`: các span PDF nằm trong hộp bao của các hàng đó
#   (hộp bao các ô Docling, cùng hệ trục PyMuPDF) và giữa mép trái/phải `left`, `right` của bảng; None khi thiếu PDF, thiếu hộp bao ô hoặc không có chữ.
# Giữ vì: header bảng chữ thuần in đậm còn dữ liệu in thường (AES p220 "Name / Jurisdiction..." đậm, hàng p221-p222 thường): chữ thuần không có số để phân biệt
#   hàng dữ liệu với header, kiểu chữ thì có.
def bold_share(page, grid: Grid, rows, left: float, right: float):
    cells = [cell for cell in grid.cells if cell.row in rows]
    if page is None or not cells:
        return None
    clip = fitz.Rect(left - 1, min(cell.t for cell in cells), right + 1, max(cell.b for cell in cells))
    bold = total = 0
    for block in page.get_text("dict", clip=clip)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                size = len(span["text"].strip())
                total += size
                if span["flags"] & 16 or "bold" in span["font"].lower():
                    bold += size
    return bold / total if total else None


# Ý nghĩa: lỗi 14. Bảng `below` (đầu trang `page`) có kề sát bảng `above` (cuối trang `page - 1`) không: cùng mép trái/phải (cùng cột), không còn
#   dòng chữ hoặc hình nào dưới `above` trên trang trước (chú thích `footnote` thì được) và nào trên `below` trên trang sau (header điều hướng `nav_headers` thì được).
# Giữ vì: bảng bị cắt giữa chừng không có gì chen giữa; bảng mới bắt đầu ở đầu trang luôn có tiêu đề, đoạn dẫn hoặc caption phía trên.
def adjacent_tables(above: Grid, page: int, below: Grid, items: dict, nav_headers: set) -> bool:
    left, _, right, bottom = above.extent[page - 1]
    left_next, top, right_next, _ = below.extent[page]
    return (abs(left - left_next) <= CONTINUED_EDGE_TOLERANCE and abs(right - right_next) <= CONTINUED_EDGE_TOLERANCE
            and not any(t >= bottom - CONTINUED_VERTICAL_SLACK and label != "footnote" for t, _, label, _ in items.get(page - 1, []))
            and not any(b <= top + CONTINUED_VERTICAL_SLACK and key not in nav_headers for _, b, _, key in items.get(page, [])))


# Ý nghĩa: lỗi 14. Bảng cuối của một trang để trang sau kế thừa: số trang, lưới Docling, header đã sửa (hàng đầu của khối), tỉ lệ chữ đậm của header GỐC của bảng
#   và của các hàng thân của trang này (None khi không đo được).
# Giữ vì: header lấy từ trang ĐÃ sửa nên bảng nhiều trang kế thừa dây chuyền; kiểu chữ của header gốc đi theo dây chuyền vì trang giữa chỉ có hàng dữ liệu.
class Tail(NamedTuple):
    page: int
    grid: Grid
    header: list
    header_bold: float | None
    body_bold: float | None


# Ý nghĩa: lỗi 14. Bảng đầu trang `page` có hàng đầu là hàng dữ liệu theo kiểu chữ không: header gốc của bảng vắt trang `tail` đậm, thân trang trước thường,
#   còn các hàng header-giả (`headers` hàng lưới đầu) của bảng này thường.
def styled_as_data(tail: Tail, grid: Grid, headers: int, page, number: int) -> bool:
    first = bold_share(page, grid, range(headers), grid.extent[number][0], grid.extent[number][2])
    return (first is not None and tail.header_bold is not None and tail.body_bold is not None
            and tail.header_bold >= BOLD_HEADER_MIN and first <= BOLD_DATA_MAX and tail.body_bold <= BOLD_BODY_MAX)


# Ý nghĩa: lỗi 14. Chèn hàng `header` lên đầu khối bảng `block` (chỉ số dòng của khối trong `lines`): [hàng đầu, dòng ngăn, ...] thành [header, dòng ngăn, hàng đầu, ...].
def insert_header(lines: list[str], block: list[int], header: list[str]) -> None:
    lines[block[0]:block[1] + 1] = ["| " + " | ".join(header) + " |", lines[block[1]], lines[block[0]]]


# Ý nghĩa: lỗi 14. Cho trang `number` đã sửa (`text`; `source` = Markdown gốc của trang để ghép lưới Docling; `page` = trang PDF để đo kiểu chữ, có thể None) và `tail` của
#   trang trước: với mỗi khối bảng có hàng đầu là hàng dữ liệu mà Docling lấy làm header (Markdown bắt buộc có header):
#   (a) hàng có giá trị đầu tiên là hàng số liệu (`is_data_row`), hoặc (b) bảng đầu trang kề sát bảng cuối trang trước, header gốc của bảng ấy đậm còn hàng này và thân
#   trang trước in thường (`styled_as_data`).
#   Nếu bảng đầu trang kề sát bảng cuối trang trước và header trang trước dùng được (`usable_header`) thì chép nguyên văn header đó lên trên (counts `continued`);
#   không thì, khi chính hàng đầu là hàng số liệu, chèn header trống (bảng vốn không có header: mục lục Kraft/Boeing, thù lao Block; counts `headerless`) để hàng dữ liệu không bị coi là tên cột.
#   Đếm thêm continued_skip_columns (kề sát, hàng số liệu, số cột khác) và continued_skip_header (kề sát nhưng header không dùng được). Trả (trang mới, tail mới).
# Giữ vì: không có header thì số liệu của trang sau mất tên cột (Best Buy p18) và hàng đầu bị biến thành tên cột; header chép nguyên văn nên không mất số liệu.
# Giới hạn: bảng chữ thuần mà header không đậm giữ nguyên; không đoán tên cột; hàng header không đệm theo độ rộng cột; hàng đầu trống hoàn toàn (header đã trống) không đổi;
#   hàng đầu chỉ có nhãn (đơn vị "In millions", câu dẫn, tên mục) không phải hàng dữ liệu nên không được thay bằng header trống (nó giữ vai trò tiêu đề/đơn vị của bảng).
def carry_header(text: str, source: str, number: int, grids: list, tail, items: dict, nav_headers: set, counts: Counter, pdf=None):
    matched = matched_blocks(source, grids)
    lines = text.split("\n")
    blocks = table_blocks(lines)
    page = pdf[number - 1] if pdf is not None and 1 <= number <= len(pdf) else None
    added: dict[int, tuple] = {}
    for k, block in enumerate(blocks):
        rows = [row_cells(lines[i]) for i in block[:1] + block[2:]]
        content = content_row(rows)
        if len(block) < 3 or not any(rows[0]) or content is None:
            continue
        numeric = is_data_row(content)
        grid = matched[k][1] if k < len(matched) else None
        joined = (k == 0 and grid is not None and tail is not None and tail.page == number - 1
                  and adjacent_tables(tail.grid, number, grid, items, nav_headers))
        if joined and len(tail.header) != len(rows[0]):
            if numeric:
                counts["continued_skip_columns"] += 1
            joined = False
        styled = joined and not numeric and any(rows[0][1:]) and styled_as_data(tail, grid, len(grid) - (matched[k][0] - 2), page, number)
        if not (numeric or styled):
            continue
        if joined and usable_header(tail.header, content if numeric else rows[0]):
            added[k] = (tail.header, tail.header_bold)
            counts["continued"] += 1
        else:
            if joined:
                counts["continued_skip_header"] += 1
            if is_data_row(rows[0]):
                added[k] = ([""] * len(rows[0]), None)
                counts["headerless"] += 1
    for k in sorted(added, reverse=True):
        insert_header(lines, blocks[k], added[k][0])
    blocks = table_blocks(lines)
    new_tail = None
    if matched and matched[-1][1] is not None and blocks:
        last, inserted = matched[-1][1], len(blocks) - 1 in added
        headers = 0 if inserted else len(last) - (matched[-1][0] - 2)
        left, right = last.extent[number][0], last.extent[number][2]
        header_bold = added[len(blocks) - 1][1] if inserted else bold_share(page, last, range(headers), left, right)
        new_tail = Tail(number, last, row_cells(lines[blocks[-1][0]]), header_bold, bold_share(page, last, range(headers, len(last)), left, right))
    return "\n".join(lines), new_tail


# Ý nghĩa: lỗi 15. Dòng Markdown có phải tiêu đề không: 1 đến 6 dấu "#", một dấu cách, rồi chữ.
# Giữ vì: "#1 priority" hoặc dòng chỉ có "#" không phải tiêu đề; đúng dạng `apply_heading_levels` và `restore_titles` ghi ra.
def is_heading(line: str) -> bool:
    stripped = line.lstrip()
    marks = len(stripped) - len(stripped.lstrip("#"))
    return 1 <= marks <= 6 and stripped[marks:marks + 1] == " " and bool(stripped[marks:].strip())


# Ý nghĩa: lỗi 15. Tiêu đề của bảng cuối trang Markdown `text`: tiêu đề cuối cùng nằm trên khối bảng cuối (cả dòng, bỏ khoảng trắng hai đầu, giữ nguyên số "#"); None khi trang không có bảng
#   hoặc không có tiêu đề nào nằm trên bảng cuối.
# Giữ vì: chỉ tiêu đề in ngay trên trang chứa bảng mới là tên của bảng. Lấy "tiêu đề gần nhất trong tài liệu" làm chuỗi 31 trang danh sách công ty con của AES p221-p251 mang tên
#   "SCHEDULE I NOTES TO SCHEDULE I" của p218, và "PART IV" cho các danh sách exhibit (đo 74 cặp trang, 22 tài liệu): đúng cấu trúc Docling nhưng sai tên bảng. Bảng dài nhiều trang vẫn có tên ở
#   mọi trang vì `carry_title` đặt tiêu đề lên đầu từng trang tiếp theo, nên trang sau thấy nó nằm trên bảng (chuỗi truyền qua chính dòng "(continued)").
def table_heading(text: str):
    lines = text.split("\n")
    blocks = table_blocks(lines)
    return next((line.strip() for line in reversed(lines[:blocks[-1][0]]) if is_heading(line)), None) if blocks else None


# Ý nghĩa: lỗi 15. Hàng header của hai bảng liền nhau qua trang có là một header không: từng ô bằng nhau sau `normalise` (bỏ dấu câu, khoảng trắng, hoa thường; chữ số giữ nguyên).
# Giữ vì: header lặp ở trang sau bị Docling ghép nhãn nhiều hàng hơi khác ("Exhibit - Number" / "Exhibit Number"), còn hai bảng cùng cột khác kỳ ("December 31, 2016 - Cost" / "December 31, 2017 - Cost":
#   Amazon 2017 p50-p51, mỗi bảng một năm) phải khác nhau: năm là chữ số nên còn nguyên. Không so gần đúng: đo 37 cặp kề sát, cùng số cột, TableFormer thấy header, header khác nhưng giống từ 0,9
#   (`SequenceMatcher`): 30 cặp khác ở chữ số (năm, ngày: bảng kỳ khác), 7 cặp còn lại giống chữ số; trong 7 cặp đó chỉ 3 bảng tiếp chưa nhận được (Block 2020 p89, JPM 2022 p173, Ulta 2023 p82: Adobe 2017 p103-p104
#   đã nhận bằng đường khác) và 2 là bảng khác (JPM 2022Q2 p117, 2023Q2 p128: "Gross derivative receivables" rồi "payables"): so gần đúng nhận thêm 3 bảng tiếp nhưng cũng nhận nhầm 2 bảng khác nên không dùng.
def same_header(above: list[str], below: list[str]) -> bool:
    return [normalise(cell) for cell in above] == [normalise(cell) for cell in below]


# Ý nghĩa: lỗi 15. Bảng đầu trang `number` (khối Markdown đầu của `text` đã qua `carry_header`; `source` + `grids` để ghép lưới Docling) có phải phần tiếp của bảng cuối trang trước `tail` không:
#   kề sát qua trang (`adjacent_tables`), cùng số cột, và hoặc header giống header của `tail` (`same_header`: PDF in lại header, hoặc `carry_header` vừa chép lên) hoặc TableFormer không gắn nhãn
#   header cho ô nào của bảng (`Grid.has_header` False: bảng chữ thuần như mục lục exhibit, danh sách công ty con, mọi hàng là dữ liệu). Đếm vào `counts`: title_pairs (là phần tiếp),
#   title_skip_columns (kề sát nhưng khác số cột), title_skip_header (kề sát, cùng số cột, header khác và TableFormer thấy header: bảng mới đứng liền sau, như bảng năm sau của Amazon p51).
# Giữ vì: kề sát cho biết không có chữ nào chen giữa nhưng bảng mới cũng có thể bắt đầu ngay đầu trang (không có tiêu đề riêng); chỉ khi chính bảng cho thấy nó là phần tiếp (header lặp hoặc không có header)
#   thì chữ "(continued)" mới đúng. Header khác mà TableFormer thấy header (ví dụ bảng năm trước / năm sau) là bảng khác nên không gắn.
# Giới hạn: header lặp lại bị Docling ghép khác hẳn (Adobe 2015 p110) không nhận ra; bảng khác số cột không xét (khác số cột thường là bảng khác, hoặc cột bị TableFormer đếm lệch).
def continued_table(text: str, source: str, number: int, grids: list, tail, items: dict, nav_headers: set, counts: Counter) -> bool:
    blocks = table_blocks(text.split("\n"))
    matched = matched_blocks(source, grids)
    grid = matched[0][1] if matched else None
    if tail is None or tail.page != number - 1 or not blocks or grid is None or not adjacent_tables(tail.grid, number, grid, items, nav_headers):
        return False
    header = row_cells(text.split("\n")[blocks[0][0]])
    if len(header) != len(tail.header):
        counts["title_skip_columns"] += 1
        return False
    if same_header(tail.header, header) or grid.has_header is False:
        counts["title_pairs"] += 1
        return True
    counts["title_skip_header"] += 1
    return False


# Ý nghĩa: lỗi 15. Đặt tiêu đề `heading` của bảng cuối trang trước (`table_heading`: dòng Markdown nguyên văn, cùng số "#") lên đầu trang `text` thành "<tiêu đề> (continued)", cách bảng một dòng trắng.
#   Tiêu đề đã có chữ "continued" (PDF in sẵn, hoặc đã đặt ở trang trước của bảng dài nhiều trang) thì giữ nguyên chữ. Chỉ khi dòng đầu có chữ của trang là hàng bảng; trang đã có tiêu đề hoặc đoạn
#   dẫn riêng (kể cả tiêu đề lỗi 23 vừa khôi phục) thì không đụng (counts title_skip_text). Đếm titled mỗi trang được đặt.
# Giữ vì: trang chia chunk theo trang hoặc cửa sổ trượt: chunk bắt đầu ở đầu trang sau chỉ có hàng bảng, không còn tên bảng ("Executive Officers" của 3M p9) nên embedding và truy xuất mất ngữ cảnh;
#   giữ nguyên cấp "#" của tiêu đề gốc nên cây tiêu đề không đổi, và chữ "continued" là dấu hiệu `stitcher.is_section_continuation` đã nhận. Không nối hàng sang trang trước: mỗi trang phải giữ đúng
#   nội dung của nó (số trang bằng chứng khi đánh giá truy xuất).
def carry_title(text: str, heading: str, counts: Counter) -> str:
    lines = text.split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or not lines[first].lstrip().startswith("|"):
        counts["title_skip_text"] += 1
        return text
    counts["titled"] += 1
    title = heading if CONTINUED_WORD in heading.lower() else f"{heading} ({CONTINUED_WORD})"
    return title + "\n\n" + "\n".join(lines[first:])
