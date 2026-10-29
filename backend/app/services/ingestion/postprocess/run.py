import json
import re
from collections import Counter
from pathlib import Path
import fitz  # PyMuPDF

from app.services.ingestion.postprocess.evidence import page_evidence
from app.services.ingestion.postprocess.text_lines import join_broken_lines, tidy_spaces
from app.services.ingestion.postprocess.small_caps import build_vocabulary, fix_small_caps
from app.services.ingestion.postprocess.grids import load_table_grids
from app.services.ingestion.postprocess.table_regrid import unspan_tables
from app.services.ingestion.postprocess.table_continued import carry_header, carry_title, continued_table, page_items, table_heading
from app.services.ingestion.postprocess.footnotes_captions import move_footnotes, split_captions
from app.services.ingestion.postprocess.headings import apply_heading_levels, drop_nav_header, load_headings, load_lost_titles, nav_headers_of, repaired_pages, restore_titles


# Ý nghĩa: chuỗi sửa cho văn bản một trang theo đúng thứ tự: bỏ bản sao ô gộp, gỡ header điều hướng, đặt cấp tiêu đề, nối dòng vỡ, gộp khoảng trắng, nối small caps.
# Giữ vì: thứ tự quan trọng (unspan_tables đầu tiên vì cần chữ ô nguyên văn; tidy_spaces sau join_broken_lines); một chỗ duy nhất để thêm
#   lỗi mới. `grids` = các bảng Docling của trang, None khi không có docling.json (bỏ qua lỗi 3).
#   `headings` = (tiêu đề Docling của trang, {loại: cấp}), None khi thiếu docling.json hoặc PDF (bỏ qua lỗi 5).
def fix_page(text: str, evidence, vocabulary: Counter, grids, nav_headers: set, headings, report: dict) -> str:
    if grids is not None:
        text = unspan_tables(text, grids, report["tables"], evidence.boxes if evidence is not None else ())
    if evidence is not None and evidence.nav_key in nav_headers:
        text = drop_nav_header(text, evidence.nav_key, report["nav_header"])
    if headings is not None:
        text = apply_heading_levels(text, *headings, report["headings"])
    text = join_broken_lines(text, evidence, report["lines"])
    text = tidy_spaces(text)
    return fix_small_caps(text, evidence, vocabulary, report["merged"], report["kept"])


# Ý nghĩa: lỗi 20. Trả `&amp;`, `&lt;`, `&gt;` về `&`, `<`, `>` (đúng ba ký tự mà bộ ghi Markdown của Docling escape).
# Giữ vì: một lượt duy nhất nên "&amp;lt;" (chữ "&lt;" thật) ra "&lt;" chứ không thành "<"; không dùng `html.unescape` vì nó cũng đổi "&reg", "&copy"
#   (không có dấu chấm phẩy) trong chữ lấy thẳng từ PDF (như URL "?a=1&region=2") thành ký hiệu.
HTML_ESCAPES = {"&amp;": "&", "&lt;": "<", "&gt;": ">"}


HTML_ESCAPE = re.compile("|".join(HTML_ESCAPES))
def unescape_markdown(text: str) -> str:
    return HTML_ESCAPE.sub(lambda m: HTML_ESCAPES[m.group()], text)


# Ý nghĩa: lỗi 19. Đổi ba ký tự Wingdings của ô tick ("þ", "ý" đã tick; "¨" trống) sang "☒" / "☐"; bỏ ô thừa ở mục danh sách "- [x]" / "- [ ]" đã nêu cùng trạng thái.
# Giữ vì: không xóa như delete_garbage.py vì mất ô nào được chọn ("Yes ý No ¨"); một ô cùng trạng thái ở đầu/cuối mục danh sách chỉ lặp lại tiền tố Docling.
#   Ô khác trạng thái với tiền tố ("- [ ] ý Accelerated filer ¨" của AMD: tiền tố Docling sai) hoặc nhiều ô trên dòng giữ nguyên, ô PDF là bằng chứng, tiền tố thì không.
# Giới hạn: chỉ ba ký tự này; "o" / "x" của Wingdings giống chữ thường nên chưa xử lý (cần vị trí PDF).
CHECKBOX_GLYPHS = str.maketrans({"þ": "☒", "ý": "☒", "¨": "☐"})


TASK_STATES = {"- [x] ": "☒", "- [ ] ": "☐"}
def fix_checkboxes(text: str, counts: Counter) -> str:
    lines = text.split("\n")
    for index, line in enumerate(lines):
        fixed = line.translate(CHECKBOX_GLYPHS)
        if fixed == line:
            continue
        counts["glyphs"] += sum(a != b for a, b in zip(line, fixed))
        state, body = TASK_STATES.get(fixed[:6]), fixed[6:].strip()
        if state and body.count("☒") + body.count("☐") == 1:
            if body.endswith(state) and body[-2:-1].isspace():
                fixed = fixed[:6] + body[:-1].rstrip()
                counts["redundant"] += 1
            elif body.startswith(state) and body[1:2].isspace():
                fixed = fixed[:6] + body[1:].lstrip()
                counts["redundant"] += 1
        lines[index] = fixed
    return "\n".join(lines)


# Ý nghĩa: sửa toàn bộ một tài liệu: mở PDF, sửa từng trang, ghi trang + full.md + fix_report.json sang fixed/.
# Giữ vì: baseline raw giữ nguyên để đối chiếu; báo cáo ghi số lần nối/giữ theo lý do và các cặp small caps nối/giữ nguyên.
# Giới hạn: full.md là các trang đã sửa nối bằng dòng trắng (không còn là full.md gốc của Docling vì luật cần số trang PDF);
#   thiếu PDF thì bỏ qua bằng chứng PDF (chỉ nối được ngắt dòng cứng, không nối small caps).
def process(doc_dir: Path, pdf_dir: Path, fixed_dir: Path) -> dict:
    pdf_path = pdf_dir / f"{doc_dir.name}.pdf"
    pdf = fitz.open(pdf_path) if pdf_path.exists() else None
    cache: dict = {}
    json_path = doc_dir / "docling.json"
    data = json.loads(json_path.read_text(encoding="utf-8")) if json_path.exists() else None
    grids = load_table_grids(data) if data is not None else None
    heading_entries, heading_levels = load_headings(data, pdf) if data is not None and pdf is not None else ({}, None)
    report = {"doc": doc_dir.name, "pdf_found": pdf is not None, "docling_json_found": grids is not None,
              "lines": Counter(), "merged": Counter(), "kept": Counter(), "tables": Counter(), "unmatched_table_pages": [], "nav_header": Counter(),
              "headings": Counter(), "cross_page": Counter(), "empty_pages_filled": [], "continued_pages": [], "headerless_pages": [], "titles": Counter(), "title_pages": [],
              "footnotes": Counter(), "footnote_pages": [], "checkboxes": Counter(), "titled_pages": [], "captions": Counter(), "caption_pages": []}
    items = page_items(data) if data is not None else {}
    titles = load_lost_titles(data, pdf, grids, items, report["titles"]) if heading_levels is not None else {}
    tail = None
    heading = None
    out = fixed_dir / doc_dir.name
    (out / "pages").mkdir(parents=True, exist_ok=True)
    fixed_pages = []
    page_files = sorted((doc_dir / "pages").glob("page_*.md"))
    nav_headers = nav_headers_of(pdf, cache)
    repaired = repaired_pages(json_path, report["cross_page"]) if data is not None else {}
    report["nav_headers"] = sorted(nav_headers)
    vocabulary = build_vocabulary([f.read_text(encoding="utf-8") for f in page_files])
    for page_file in page_files:
        pdf_page = int(page_file.stem[len("page_"):])
        unmatched = report["tables"]["unmatched"]
        raw = page_file.read_text(encoding="utf-8")
        if pdf_page in repaired and repaired[pdf_page].strip() and not raw.strip():
            report["empty_pages_filled"].append(pdf_page)
        source = repaired.get(pdf_page, raw)
        text = fix_page(source, page_evidence(pdf, cache, pdf_page), vocabulary,
                        None if grids is None else grids.get(pdf_page, []), nav_headers,
                        None if heading_levels is None else (heading_entries.get(pdf_page, []), heading_levels), report)
        if report["tables"]["unmatched"] > unmatched:
            report["unmatched_table_pages"].append(pdf_page)
        continues = False
        if grids is not None:
            captioned = report["captions"]["captioned"]
            text = split_captions(text, source, grids.get(pdf_page, []), report["captions"], pdf[pdf_page - 1] if pdf is not None and 1 <= pdf_page <= len(pdf) else None, heading_levels)
            if report["captions"]["captioned"] > captioned:
                report["caption_pages"].append(pdf_page)
            continued, headerless = report["tables"]["continued"], report["tables"]["headerless"]
            previous = tail
            text, tail = carry_header(text, source, pdf_page, grids.get(pdf_page, []), tail, items, nav_headers, report["tables"], pdf)
            continues = continued_table(text, source, pdf_page, grids.get(pdf_page, []), previous, items, nav_headers, report["tables"])
            if report["tables"]["continued"] > continued:
                report["continued_pages"].append(pdf_page)
            if report["tables"]["headerless"] > headerless:
                report["headerless_pages"].append(pdf_page)
            moved = report["footnotes"]["moved"]
            text = move_footnotes(text, source, grids.get(pdf_page, []), report["footnotes"], pdf[pdf_page - 1] if pdf is not None and 1 <= pdf_page <= len(pdf) else None, pdf_page, heading_levels)
            if report["footnotes"]["moved"] > moved:
                report["footnote_pages"].append(pdf_page)
        if pdf_page in titles:
            restored = report["titles"]["restored"]
            text = restore_titles(text, titles[pdf_page], heading_levels, report["titles"])
            if report["titles"]["restored"] > restored:
                report["title_pages"].append(pdf_page)
        if continues:
            if heading is None:
                report["tables"]["title_skip_none"] += 1
            else:
                titled = report["tables"]["titled"]
                text = carry_title(text, heading, report["tables"])
                if report["tables"]["titled"] > titled:
                    report["titled_pages"].append(pdf_page)
        text = fix_checkboxes(unescape_markdown(text), report["checkboxes"])
        heading = table_heading(text)
        (out / "pages" / page_file.name).write_text(text, encoding="utf-8")
        fixed_pages.append(text.strip())
    (out / "full.md").write_text("\n\n".join(p for p in fixed_pages if p) + "\n", encoding="utf-8")
    for key in ("lines", "merged", "kept", "tables", "nav_header", "headings", "cross_page", "titles", "footnotes", "checkboxes", "captions"):
        report[key] = dict(report[key].most_common())
    (out / "fix_report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report
