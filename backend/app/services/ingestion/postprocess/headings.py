from collections import Counter
from pathlib import Path
import fitz  # PyMuPDF
from docling_core.types.doc import DoclingDocument

from app.services.ingestion.postprocess.constants import CONTINUED_VERTICAL_SLACK, HEADING_STYLE_MIN_COUNT, HEADING_STYLE_MIN_SHARE, LEADING_PUNCT, NAV_HEADER_MIN_PAGES, TITLE_WORDS, TRAILING_PUNCT
from app.services.ingestion.postprocess.evidence import normalise, page_evidence
from app.services.ingestion.postprocess.grids import page_span
from app.services.ingestion.postprocess.tokens import letters


# Ý nghĩa: các header điều hướng chạy của tài liệu: `nav_key` của dòng trên cùng xuất hiện ở NAV_HEADER_MIN_PAGES trang trở lên.
def nav_headers_of(pdf, cache: dict) -> set[str]:
    if pdf is None:
        return set()
    counts = Counter(page_evidence(pdf, cache, n).nav_key for n in range(1, len(pdf) + 1))
    return {key for key, pages in counts.items() if key and pages >= NAV_HEADER_MIN_PAGES}


# Ý nghĩa: lỗi 4. Ở trang có header điều hướng `key`, gỡ phần tử đầu tiên của trang Markdown nếu nó là chính header đó: tiêu đề "#..." bị
#   xóa (cùng dòng trắng theo sau); hàng header của bảng ("| Table of Contents | |") được làm trống đúng độ rộng. Đếm vào `counts`.
# Giữ vì: "## Table of Contents" ở đầu trang làm RAG khớp nhầm hàng chục trang; hàng header bị thay bằng chữ này làm mất tên cột bảng.
# Giới hạn: chỉ xét phần tử đầu tiên của trang (đúng vị trí dòng chữ trên cùng trong PDF); hàng header bị làm trống để lại bảng không có
#   tên cột (trang tiếp theo của bảng nhiều trang vốn không có tên cột thật), việc điền tên cột là việc của bước header bảng.
def drop_nav_header(text: str, key: str, counts: Counter) -> str:
    lines = text.split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return text
    line = lines[first]
    if line.startswith("#") and normalise(line) == key:
        del lines[first:first + 2 if first + 1 < len(lines) and not lines[first + 1].strip() else first + 1]
        counts["heading_removed"] += 1
    elif line.lstrip().startswith("|"):
        parts = line.split("|")
        hits = [i for i, part in enumerate(parts) if part.strip() and normalise(part) == key]
        if hits:
            for i in hits:
                parts[i] = " " * len(parts[i])
            lines[first] = "|".join(parts)
            counts["table_header_blanked"] += 1
    return "\n".join(lines)


# Ý nghĩa: kiểu chữ của một span PDF: (cỡ làm tròn 0.5, bold, nghiêng).
def span_style(span: dict) -> tuple:
    font = span["font"].lower()
    return (round(span["size"] * 2) / 2, bool(span["flags"] & 16) or "bold" in font, bool(span["flags"] & 2) or "italic" in font or "oblique" in font)


# Ý nghĩa: kiểu chữ của chữ đầu tiên trong hộp bao của một tiêu đề Docling, đọc từ PDF: (cỡ làm tròn 0.5, bold, nghiêng); không có chữ thì None.
# Giữ vì: kiểu chữ là bằng chứng cấp tiêu đề con (AMCOR: nhóm rủi ro bold, từng rủi ro bold-nghiêng). Chỉ lấy chữ đầu vì tiêu đề chạy liền
#   thân ("Raw Materials - Price fluctuations...") có phần thân khác kiểu.
# Giới hạn: hộp bao Docling (gốc dưới-trái hoặc trên-trái) đổi sang tọa độ PyMuPDF; chữ lấn từ khối bên cạnh vào hộp có thể bị lấy nhầm.
def heading_style(page, bbox: dict):
    top, bottom = bbox["t"], bbox["b"]
    if bbox.get("coord_origin") == "BOTTOMLEFT":
        top, bottom = page.rect.height - top, page.rect.height - bottom
    clip = fitz.Rect(bbox["l"] - 1, top - 1, bbox["r"] + 1, bottom + 1)
    for block in page.get_text("dict", clip=clip)["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    return span_style(span)
    return None


# Ý nghĩa: loại của một tiêu đề: ("part",) nếu là "PART <số La Mã>", ("item",) nếu là "Item <số...>", còn lại None (xếp theo kiểu chữ).
# Giữ vì: tên Part/Item là cấu trúc bắt buộc của mẫu SEC, kiểu chữ PDF không phân biệt được với tiêu đề thường cùng cỡ; so từng từ, không regex.
# Giới hạn: "PART" chỉ tính khi tiêu đề ngắn (<= 8 từ) và từ sau là I..IV; "Item" cần từ sau bắt đầu bằng chữ số ("1A.", "5.02").
def heading_kind(text: str):
    words = text.split()
    tokens = [word.strip(".,:;-–—") for word in words]
    if len(tokens) > 1 and tokens[0].upper() == "PART" and tokens[1].upper() in ("I", "II", "III", "IV") and len(words) <= 8:
        return ("part",)
    if len(tokens) > 1 and tokens[0].upper() == "ITEM" and tokens[1][:1].isdigit():
        return ("item",)
    return None


# Ý nghĩa: thứ tự cấp của một loại tiêu đề (nhỏ = cấp cao): Part, Item, rồi kiểu chữ (cỡ lớn, bold, không nghiêng trước), rồi không có kiểu chữ.
def heading_rank_key(kind) -> tuple:
    if kind == ("part",):
        return (0,)
    if kind == ("item",):
        return (1,)
    if kind is None:
        return (3,)
    size, bold, italic = kind
    return (2, -size, not bold, italic)


# Ý nghĩa: lỗi 5, bước 1. Từ docling.json và PDF: {số trang: [(chữ tiêu đề đã chuẩn hóa, loại)]} theo thứ tự đọc, và {loại: cấp} liên tục
#   (1 = cao nhất) chỉ tính các loại có mặt trong tài liệu.
# Giữ vì: cấp là thứ hạng trong tài liệu (không cố định theo cỡ chữ vì cỡ khác nhau giữa tài liệu); cần PDF nên không có PDF thì không làm.
def load_headings(data: dict, pdf):
    by_page: dict[int, list] = {}
    for item in data["texts"]:
        if item["label"] != "section_header" or not item["prov"]:
            continue
        prov = item["prov"][0]
        kind = heading_kind(item["text"])
        if kind is None and 1 <= prov["page_no"] <= len(pdf):
            kind = heading_style(pdf[prov["page_no"] - 1], prov["bbox"])
        by_page.setdefault(prov["page_no"], []).append((normalise(item["text"]), kind))
    counts = Counter(kind for entries in by_page.values() for _, kind in entries if kind and len(kind) == 3)
    if counts:
        kept = [style for style, n in counts.items() if n >= max(HEADING_STYLE_MIN_COUNT, HEADING_STYLE_MIN_SHARE * sum(counts.values()))]
        kept = kept or [counts.most_common(1)[0][0]]
        nearest = {style: min(kept, key=lambda k: (abs(k[0] - style[0]), k[1] != style[1], k[2] != style[2])) for style in counts}
        for page_no, entries in by_page.items():
            by_page[page_no] = [(key, nearest.get(kind, kind)) for key, kind in entries]
    kinds = sorted({kind for entries in by_page.values() for _, kind in entries}, key=heading_rank_key)
    return by_page, {kind: rank for rank, kind in enumerate(kinds, 1)}


# Ý nghĩa: lỗi 5, bước 2. Ghép từng dòng "## chữ" của trang Markdown (theo thứ tự) với tiêu đề Docling của trang rồi đổi số "#" theo cấp.
# Giữ vì: breadcrumb PART I > Item 1A > nhóm rủi ro > rủi ro cần cấp thật; ghép theo thứ tự + chữ nên tiêu đề lặp chữ vẫn ghép đúng.
# Giới hạn: dòng không ghép được giữ "##" và đếm `unmatched`. Chạy trước các bước sửa chữ (cần chữ tiêu đề nguyên văn).
def apply_heading_levels(text: str, entries: list, levels: dict, counts: Counter) -> str:
    lines = text.split("\n")
    start = 0
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        key = normalise(line[3:])
        found = next((k for k in range(start, len(entries)) if entries[k][0] == key), None)
        if found is None:
            counts["unmatched"] += 1
            continue
        start = found + 1
        level = levels[entries[found][1]]
        lines[i] = "#" * min(level + 1, 6) + line[2:]
        counts[f"level_{level}"] += 1
    return "\n".join(lines)


# Ý nghĩa: lỗi 23. Các dòng chữ PDF nằm trong hộp bao `bbox` của một mục Docling có chữ `text`, từ trên xuống: [(chữ một dòng, kiểu chữ của chữ đầu dòng)].
# Giữ vì: Docling gộp "Consolidated Statements of Income" (10 pt đậm) và "Verizon Communications Inc. and Subsidiaries" (9 pt đậm) làm một mục `page_header`; tách theo dòng PDF thì mỗi dòng
#   có kiểu chữ riêng (Pfizer: tiêu đề 8,5 pt đậm, tên công ty 7 pt thường) để biết dòng nào là tiêu đề.
# Giới hạn: chữ các dòng PDF ghép lại phải bằng `text` (so bằng `normalise`); không bằng (dòng khác lọt vào hộp, hai cột chung một dòng) thì trả cả `text` làm một dòng, kiểu chữ của chữ đầu tiên.
def title_lines(page, bbox: dict, text: str) -> list[tuple[str, tuple | None]]:
    top, bottom = page_span(bbox, page.rect.height)
    clip = fitz.Rect(bbox["l"] - 1, top - 1, bbox["r"] + 1, bottom + 1)
    found = []
    for block in page.get_text("dict", clip=clip)["blocks"]:
        for line in block.get("lines", []):
            spans = [span for span in line["spans"] if span["text"].strip()]
            if spans:
                found.append((line["bbox"][1], " ".join("".join(span["text"] for span in spans).split()), span_style(spans[0])))
    found.sort(key=lambda entry: entry[0])
    if normalise("".join(line for _, line, _ in found)) != normalise(text):
        return [(" ".join(text.split()), heading_style(page, bbox))]
    return [(line, style) for _, line, style in found]


# Ý nghĩa: lỗi 23, bước 1. Từ docling.json và PDF: {số trang: [(dòng chữ, kiểu chữ)]} của các tiêu đề báo cáo tài chính mà Docling gán `page_header` (bị bỏ khỏi Markdown). Đếm vào `counts`: lý do bỏ
#   mục (running = in ở nhiều trang, no_table = trang không có bảng, position = có phần tử khác nằm trên nó).
# Giữ vì: xem điều kiện ở docstring đầu file. `grids` = {trang: [lưới bảng]} (`load_table_grids`), `items` = `page_items`; "nằm trên mọi phần tử" so đáy của mục với đỉnh của phần tử cao nhất
#   (chữ, hình hoặc bảng không phải furniture) trên trang: mục `page_header` không nằm ở đầu trang thì chèn lên đầu trang là sai chỗ.
# Giới hạn: chỉ mục một trang; "in ở nhiều trang" đếm theo chữ cái, mọi nhãn Docling (header chạy được Docling gán `text` ở trang khác vẫn tính); tiêu đề không có từ trong TITLE_WORDS không xét.
def load_lost_titles(data: dict, pdf, grids: dict, items: dict, counts: Counter) -> dict[int, list]:
    heights = {int(page): info["size"]["height"] for page, info in data["pages"].items()}
    printed: dict[str, set] = {}
    for item in data["texts"]:
        printed.setdefault(letters(item["text"]), set()).update(prov["page_no"] for prov in item["prov"])
    titles: dict[int, list] = {}
    for item in data["texts"]:
        if item["label"] != "page_header" or len(item["prov"]) != 1:
            continue
        if not {word.strip(LEADING_PUNCT + TRAILING_PUNCT).upper() for word in item["text"].split()} & TITLE_WORDS:
            continue
        prov = item["prov"][0]
        number = prov["page_no"]
        if len(printed[letters(item["text"])]) >= NAV_HEADER_MIN_PAGES:
            counts["running"] += 1
        elif not grids.get(number) or not 1 <= number <= len(pdf):
            counts["no_table"] += 1
        elif page_span(prov["bbox"], heights[number])[1] > min([top for top, _, _, _ in items.get(number, [])] + [grid.extent[number][1] for grid in grids[number]]) + CONTINUED_VERTICAL_SLACK:
            counts["position"] += 1
        else:
            titles.setdefault(number, []).extend(title_lines(pdf[number - 1], prov["bbox"], item["text"]))
    return titles


# Ý nghĩa: lỗi 23. Cấp (1 = cao nhất) của một dòng tiêu đề khôi phục có `kind` (("part",), ("item",) hoặc kiểu chữ PDF): cấp của đúng loại đó nếu tài liệu có; không thì của kiểu chữ gần nhất
#   (cỡ, rồi bold, rồi nghiêng, như `load_headings`); tài liệu không có kiểu chữ nào thì sâu hơn mọi cấp hiện có.
# Giữ vì: cấp là thứ hạng trong tài liệu (lỗi 5), nên tiêu đề khôi phục cùng cấp với tiêu đề cùng kiểu chữ Docling đã nhận (Verizon 2021 p51: tên công ty `######`, tiêu đề khôi phục cao hơn nó).
#   Kiểu chữ hiếm đã bị `load_headings` gộp vào kiểu gần nhất nên không có trong `levels` (Pfizer: 8,5 pt đậm gộp vào 8 pt đậm = cấp 4, như các tiêu đề báo cáo Docling nhận ở p58, p60, p61).
def title_level(kind, levels: dict) -> int:
    if kind in levels:
        return levels[kind]
    styles = [style for style in levels if style and len(style) == 3]
    if len(kind) == 3 and styles:
        return levels[min(styles, key=lambda style: (abs(style[0] - kind[0]), style[1] != kind[1], style[2] != kind[2]))]
    return max(levels.values(), default=0) + 1


# Ý nghĩa: lỗi 23, bước 2. Đặt các dòng tiêu đề khôi phục `lines` ([(chữ, kiểu chữ)]) lên đầu trang Markdown `text`, mỗi dòng cách nhau một dòng trắng: dòng là tên Part/Item hoặc in đậm thành tiêu đề
#   ("#" * (cấp + 1), như `apply_heading_levels`), dòng khác là chữ thường; dòng nào có chữ đã nằm trên trang (tiêu đề Docling đã nhận, ô header bảng) thì bỏ. Đếm vào `counts`: restored (trang), lines, present.
# Giữ vì: làm SAU `fix_page`/`carry_header` để không đổi dòng đầu trang mà lỗi 4 và lỗi 14 dựa vào; "đã có trên trang" so cả trang đã chuẩn hóa (chữ có ở đâu cũng không lặp lại).
# Giới hạn: tiêu đề nằm trong đoạn văn bản chứa cụm đó thì cũng coi là đã có (không khôi phục: giữ nguyên an toàn hơn lặp).
def restore_titles(text: str, lines: list, levels: dict, counts: Counter) -> str:
    present = normalise(text)
    added = []
    for line, style in lines:
        if normalise(line) in present:
            counts["present"] += 1
            continue
        kind = heading_kind(line) or style
        if kind and (len(kind) == 1 or kind[1]):
            line = "#" * min(title_level(kind, levels) + 1, 6) + " " + line
        added.append(line)
    if added:
        counts["restored"] += 1
        counts["lines"] += len(added)
    return "\n\n".join(added + [text])


# Ý nghĩa: các phần của một đoạn văn vắt trang theo từng trang: {số trang: (chữ của đoạn trên trang đó, các prov của trang đó)}.
# Giữ vì: điểm cắt giữa hai trang là charspan bắt đầu của prov đầu tiên trên trang sau, dịch về ranh giới từ gần nhất (`snap_to_word`);
#   các phần ghép lại đúng bằng `text`. charspan lệch vài ký tự khi Docling bỏ dấu gạch nối cuối dòng khỏi `text` (JPM "loss-absorbing"
#   thành "lossabsorbing", AMCOR "-8 awarded"), không dịch thì một từ bị cắt làm đôi giữa hai trang. Phần rỗng không tính là một trang.
def page_segments(item) -> dict[int, tuple[str, list]]:
    by_page: dict[int, list] = {}
    for prov in item.prov:
        by_page.setdefault(prov.page_no, []).append(prov)
    pages = list(by_page)
    cuts = [0] + [snap_to_word(item.text, min(prov.charspan[0] for prov in by_page[page])) for page in pages[1:]] + [len(item.text)]
    segments = {page: (item.text[cuts[k]:cuts[k + 1]].strip(), by_page[page]) for k, page in enumerate(pages)}
    return {page: segment for page, segment in segments.items() if segment[0]}


# Ý nghĩa: vị trí `index` trong `text` dịch về chỗ giữa hai từ gần nhất (đứng cạnh khoảng trắng, hoặc đầu/cuối chuỗi); hòa thì về phía trước.
def snap_to_word(text: str, index: int) -> int:
    index = max(0, min(index, len(text)))
    if index in (0, len(text)) or text[index - 1].isspace() or text[index].isspace():
        return index
    left = index
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = index
    while right < len(text) and not text[right].isspace():
        right += 1
    return left if index - left <= right - index else right


# Ý nghĩa: lỗi 8. Từ docling.json: {số trang: Markdown của trang} cho mọi trang có phần của một đoạn văn vắt trang, mỗi đoạn được cắt theo
#   `page_segments` và đặt vào đúng trang của nó. Đếm vào `counts`: items_split, pages_rewritten.
# Giữ vì: docling-core `export_to_markdown(page_no=N)` giữ phần tử khi `item.prov[0].page_no == N` (serializer/common.py), nên cả đoạn vào
#   trang đầu và trang sau mất chữ (JPM p351, AMCOR p5 thành file 0 byte dù PDF có chữ). Xuất lại bằng chính bộ ghi Markdown của Docling
#   (xuống dòng, thoát ký tự, thứ tự trong cây tài liệu giữ nguyên) thay vì cắt chuỗi Markdown, vì thoát ký tự làm chữ Markdown khác `text`.
# Giới hạn: chỉ đoạn `text` (cả 238 đoạn vắt trang của 10 tài liệu đều là `text`; tiêu đề, danh sách, bảng không vắt trang). Phần đuôi ở
#   trang sau là đoạn riêng bắt đầu giữa câu, chưa nối lại với phần đầu; trang chỉ được xuất lại khi có đoạn vắt trang đi qua nó.
def repaired_pages(json_path: Path, counts: Counter) -> dict[int, str]:
    document = DoclingDocument.load_from_json(json_path)
    split = [(item, page_segments(item)) for item in document.texts if len({prov.page_no for prov in item.prov}) > 1]
    counts["items_split"] = len(split)
    pages: dict[int, str] = {}
    for page in sorted({page for _, segments in split for page in segments}):
        touching = [(item, segments[page]) for item, segments in split if page in segments]
        original = [(item, item.text, item.prov) for item, _ in touching]
        for item, (segment, provs) in touching:
            item.text, item.prov = segment, provs
        pages[page] = document.export_to_markdown(page_no=page)
        for item, text, prov in original:
            item.text, item.prov = text, prov
    counts["pages_rewritten"] = len(pages)
    return pages
