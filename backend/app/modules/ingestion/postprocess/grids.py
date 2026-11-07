from typing import NamedTuple



# Ý nghĩa: chữ của một ô lưới Docling đúng như bộ ghi Markdown của Docling viết ra (xuống dòng -> dấu cách, "|" -> "&#124;"), bỏ khoảng
#   trắng hai đầu để so với ô Markdown đã bỏ đệm.
# Giữ vì: so khớp bảng Markdown với bảng Docling phải nguyên văn; chỉ một chỗ định nghĩa "chữ của ô".
def grid_cell_text(cell: dict) -> str:
    return (cell["text"] or "").replace("\n", " ").replace("|", "&#124;").strip()


# Ý nghĩa: một ô của bảng Docling với hộp bao (hàng, cột bắt đầu, số hàng và số cột phủ, chữ, trái, trên, phải, dưới; gốc toạ độ trên-trái như PDF).
class TableCell(NamedTuple):
    row: int
    col: int
    row_span: int
    col_span: int
    text: str
    l: float
    t: float
    r: float
    b: float


# Ý nghĩa: lưới Docling (list hàng, mỗi ô là (chữ, cột bắt đầu của ô gốc)) kèm `cells`: các TableCell của bảng; rỗng khi không có hộp bao dùng được;
#   `extent`: {số trang: (trái, trên, phải, dưới)} của bảng, tính từ mép trên trang (lỗi 14);
#   và `has_header`: TableFormer có gắn nhãn "ô header cột" (`column_header`) cho ô nào của bảng không (lỗi 15); None khi không biết.
class Grid(list):
    cells: tuple = ()
    extent: dict = {}
    has_header: bool | None = None


# Ý nghĩa: hộp bao Docling (gốc dưới-trái hoặc trên-trái) -> (trên, dưới) tính từ mép trên trang, cùng hệ trục với PyMuPDF.
def page_span(bbox: dict, height: float) -> tuple[float, float]:
    top, bottom = bbox["t"], bbox["b"]
    return (height - top, height - bottom) if bbox.get("coord_origin") == "BOTTOMLEFT" else (top, bottom)


# Ý nghĩa: từ docling.json đã đọc, trả {số trang: [lưới bảng]} theo thứ tự tài liệu; lưới = Grid, mỗi ô lưới là (chữ, cột bắt đầu của ô gốc).
# Giữ vì: `start_col_offset_idx` của ô lưới là bằng chứng ô gộp ngang (Docling lặp cùng một ô gốc vào mọi cột nó phủ); hộp bao các ô là
#   bằng chứng hàng và nhãn cho lỗi 12; hộp bao cả bảng (`prov`) là bằng chứng bảng kề nhau qua trang cho lỗi 14; nhãn `column_header` của các ô cho biết TableFormer có thấy hàng header nào không (lỗi 15).
#   Bảng có `prov` ở nhiều trang được ghi ở từng trang.
def load_table_grids(data: dict) -> dict[int, list[Grid]]:
    by_page: dict[int, list] = {}
    heights = {int(page): info["size"]["height"] for page, info in data["pages"].items()}
    for table in data["tables"]:
        grid = Grid([[(grid_cell_text(cell), cell["start_col_offset_idx"]) for cell in row] for row in table["data"]["grid"]])
        boxes = [cell.get("bbox") for cell in table["data"]["table_cells"]]
        if all(box and box.get("coord_origin") == "TOPLEFT" for box in boxes):
            grid.cells = tuple(TableCell(cell["start_row_offset_idx"], cell["start_col_offset_idx"], cell["row_span"], cell["col_span"],
                                         grid_cell_text(cell), box["l"], box["t"], box["r"], box["b"])
                               for cell, box in zip(table["data"]["table_cells"], boxes))
        if all("column_header" in cell for cell in table["data"]["table_cells"]):
            grid.has_header = any(cell["column_header"] for cell in table["data"]["table_cells"])
        grid.extent = {}
        for prov in table["prov"]:
            top, bottom = page_span(prov["bbox"], heights[prov["page_no"]])
            grid.extent[prov["page_no"]] = (prov["bbox"]["l"], top, prov["bbox"]["r"], bottom)
        for page_no in sorted({prov["page_no"] for prov in table["prov"]}):
            by_page.setdefault(page_no, []).append(grid)
    return by_page


# Ý nghĩa: các khối bảng Markdown của một trang: mỗi khối là danh sách chỉ số dòng liền nhau bắt đầu bằng "|" (cùng quy ước STRUCTURE_PREFIXES).
def table_blocks(lines: list[str]) -> list[list[int]]:
    blocks: list[list[int]] = []
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        if blocks and blocks[-1][-1] == i - 1:
            blocks[-1].append(i)
        else:
            blocks.append([i])
    return blocks


# Ý nghĩa: các ô của một dòng bảng Markdown, bỏ đệm.
def row_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]
