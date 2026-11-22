"""F3 (21/11/2026): a table the PDF prints but the parse lost is rebuilt from the PDF words. Repair only: it runs where a detector says the page lost
a table (written as one-value paragraphs, or the whole table in one Markdown cell), never on a table the parse already has.

Measured on the 134 study documents (experiments/results/docs/parsing/audit_rebuild_v2_2026-11-21.md, ocr_vs_rebuild_2026-11-21.md, heldout_rebuild_*):
24 flagged pages, 244 true table rows: parse 13 exact, this rebuild 234, Chandra OCR 201. On 400 tables the parse reads right the rebuild keeps 95.6 %
of the rows but only 88 % of the column counts and returns one table 93 % of the time: hence repair only.
"""
import re
from collections import Counter

from app.modules.ingestion.postprocess.constants import TEXT_FOLD, VALUE_PREFIXES, VALUE_SUFFIXES
from app.modules.ingestion.postprocess.evidence import glue_superscripts
from app.modules.ingestion.postprocess.grids import row_cells, table_blocks
from app.modules.ingestion.postprocess.table_regrid import render_table
from app.modules.ingestion.postprocess.table_values import continues_label, phrase_cells, split_signs
from app.modules.ingestion.postprocess.tokens import is_marker, is_text_word

# Ý nghĩa: hai mép phải (tại chữ số cuối) cách nhau không quá ngần này điểm là cùng một cột giá trị.
# Giữ vì: báo cáo căn số lề phải; dấu ")" của số âm thò ra 2-3 điểm. Đo trên 24 trang lỗi và 400 bảng đúng (21/11).
RIGHT_TOL = 4.0
# Ý nghĩa: vùng bảng mở lên/xuống qua dòng cách dòng kề không quá ngần này điểm; từ ngần này dòng bảng bị mất liên tiếp mới coi là bảng mất.
REGION_GAP = 18.0
MIN_LOST_LINES = 3
# Ý nghĩa: ô Markdown giữ từ ngần này số trở lên (và số chiếm từ một nửa số từ) là cả bảng dồn vào một ô.
COLLAPSED_MIN_NUMBERS = 15
YEARISH = re.compile(r"^\(?((19|20)\d\d|\d{1,2},)\)?$")
WORD = re.compile(r"[a-z0-9]+")


def letter_mark(token: str) -> bool:
    """Footnote mark made of letters ("(a)", "(b)(c)"): is_marker also accepts "(373)", a negative amount."""
    return is_marker(token) and not any(ch.isdigit() for ch in token)


def lines_of(words: list) -> list:
    """PDF words grouped into printed lines by their vertical centre, each line left to right."""
    words = sorted(words, key=lambda w: (w[1] + w[3]) / 2)
    out, cur, last = [], [], None
    for w in words:
        cy = (w[1] + w[3]) / 2
        if last is not None and cy - last > 0.5 * (w[3] - w[1]):
            out.append(sorted(cur, key=lambda w: w[0]))
            cur = []
        cur.append(w)
        last = cy if not cur[:-1] else (last + cy) / 2
    if cur:
        out.append(sorted(cur, key=lambda w: w[0]))
    return out


def digit_end(x0: float, x1: float, text: str) -> float:
    """Where the last digit of a word ends (a ")" or "%" glued after it left out); a word without digits ends at x1."""
    last = max((i for i, ch in enumerate(text) if ch.isdigit()), default=None)
    return x1 if last is None else x0 + (x1 - x0) * (last + 1) / len(text)


def value_groups(values: list, refs=frozenset()) -> list:
    """Values of a line as (x0, x1, tokens, number start, last-digit end): "$" and "(" join the next word, "%" and ")" the one before
    (as group_value_words), letter marks and footnote numbers printed small (`refs`) join the value before them."""
    groups: list = []
    for x0, x1, text in sorted(split_signs([(w[0], w[2], w[4]) for w in values])):
        t = text.translate(TEXT_FOLD)
        if groups and (groups[-1][2][-1] in VALUE_PREFIXES or t in VALUE_SUFFIXES):
            g = groups[-1]
            start = x0 if all(tok in VALUE_PREFIXES for tok in g[2]) else g[3]
            end = digit_end(x0, x1, t) if any(ch.isdigit() for ch in t) else g[4]
            groups[-1] = (g[0], max(g[1], x1), g[2] + [t], start, end)
        elif groups and (letter_mark(t) or (x0, x1, text) in refs):
            g = groups[-1]
            groups[-1] = (g[0], max(g[1], x1), g[2] + [t], g[3], g[4])
        else:
            groups.append((x0, x1, [t], x0, digit_end(x0, x1, t)))
    return groups


def split_line(line: list, refs=frozenset()):
    """-> (label words, value groups). The label is the line's first phrase (even "US", a placeholder for the backend) and every word before the first
    figure of the first value phrase."""
    cells = phrase_cells([(w[0], w[2], w[4]) for w in line])
    digits = lambda c: any(c[0] <= w[0] <= c[1] and any(ch.isdigit() for ch in w[4]) for w in line)
    cell = next((c for k, c in enumerate(cells) if c[2] and (k > 0 or digits(c))), None)
    cut = None
    if cell is not None:
        first = next((w for w in line if cell[0] <= w[0] <= cell[1] and (any(ch.isdigit() for ch in w[4]) or w[4] in VALUE_PREFIXES)), None)
        cut = first[0] if first is not None else cell[0]
    label = [w for w in line if cut is None or w[0] < cut]
    return label, value_groups([w for w in line if cut is not None and w[0] >= cut], refs)


def has_digit(group) -> bool:
    return any(ch.isdigit() for t in group[2] for ch in t)


def is_data(groups: list) -> bool:
    """A data row: no lowercase word among its values and 2+ figures that are not years or day numbers."""
    if any(is_text_word(t) for g in groups for t in g[2]):
        return False
    return sum(1 for g in groups if has_digit(g) and not all(YEARISH.match(t) for t in g[2] if any(c.isdigit() for c in t))) >= 2


def columns_by_right_edge(groups: list) -> list:
    """[[left, right]] per value column: last-digit ends clustered within RIGHT_TOL; left = leftmost number start of the column."""
    cols: list = []
    for end, start in sorted((g[4], g[3]) for g in groups):
        if cols and end - cols[-1][2] <= RIGHT_TOL:
            cols[-1] = [min(cols[-1][0], start), max(cols[-1][1], end), end]
        else:
            cols.append([start, end, end])
    return [[a, b] for a, b, _ in cols]


def build_one(rows: list):
    """rows [(label, groups, line, data)] of one table, header lines first -> Markdown lines, or None. Columns come from figures only (a "-" or "NM" is
    centred, not right-aligned): a figure goes to the column of its last digit, a placeholder to the column its centre is in. Header phrases name every
    column whose centre they cover; a wrapped label (next line starts in lowercase) is joined."""
    data_groups = [g for r in rows if r[3] for g in r[1] if has_digit(g)]
    if not data_groups:
        return None
    cols = columns_by_right_edge(data_groups)
    first = next(i for i, r in enumerate(rows) if r[3])
    while first > 0 and not rows[first - 1][1] and all(w[2] < cols[0][0] for w in rows[first - 1][2]):
        first -= 1  # section labels right above the first data row belong to the body
    body: list = []
    for label, groups, _, _ in rows[first:]:
        vals = [""] * len(cols)
        for g in groups:
            if has_digit(g):
                k = next((i for i, c in enumerate(cols) if c[1] - RIGHT_TOL <= g[4] <= c[1] + 1), None)
                if k is None:
                    k = min(range(len(cols)), key=lambda i: abs(cols[i][1] - g[4]))
            else:
                centre = (g[0] + g[1]) / 2
                k = next((i for i, c in enumerate(cols) if c[0] - 2 <= centre <= c[1] + 2), None)
                if k is None:
                    k = min(range(len(cols)), key=lambda i: min(abs(cols[i][0] - centre), abs(cols[i][1] - centre)))
            vals[k] = (vals[k] + " " + " ".join(g[2])).strip()
        if body and label and not any(body[-1][1:]) and continues_label(label, body[-1][0]):
            body[-1] = [body[-1][0] + " " + label] + vals
        else:
            body.append([label] + vals)
    names: list = [[] for _ in cols]
    left: list = []
    for _, _, line, _ in rows[:first]:
        for a, b, _ in phrase_cells([(w[0], w[2], w[4]) for w in line]):
            text = " ".join(w[4] for w in line if a <= w[0] and w[2] <= b)
            covered = [i for i, c in enumerate(cols) if a - 2 <= (c[0] + c[1]) / 2 <= b + 2]
            if not covered:
                if b < cols[0][0]:
                    left.append(text)
                    continue
                covered = [min(range(len(cols)), key=lambda i: abs((cols[i][0] + cols[i][1]) / 2 - (a + b) / 2))]
            for i in covered:
                names[i].append(text)
    return render_table([[" ".join(left)] + [" - ".join(n) for n in names]] + body)


# Ý nghĩa: F3. Dựng các bảng từ chữ PDF trong vùng `region` (x0, y0, x1, y1, tính từ mép trên trang): mỗi dòng in là một hàng, cột theo mép phải tại chữ số cuối;
#   tách bảng ở dòng tiêu đề giữa chừng (dòng không phải dữ liệu, từ 2 cụm chữ trên vùng số) khi phần dưới đổi cách chia cột. Trả [dòng Markdown của từng bảng].
# Giữ vì: lớp chữ PDF vẫn đủ vị trí từng từ khi Docling bỏ sót bảng hoặc dồn cả bảng vào một ô.
# Giới hạn: tiêu đề phủ nhiều cột chỉ gắn vào cột nằm dưới nó; bảng nhiều chữ (diện tích MGM 2016 p212) dựng kém; glue_superscripts chỉ dùng để biết từ nào là
#   số chú thích in nhỏ (nó kéo dài hộp chữ của số, mép phải lấy từ hộp gốc).
def rebuild(words: list, region: tuple) -> list:
    x0, y0, x1, y1 = region
    glued = glue_superscripts(words)
    reach = {g[2] for o, g in zip(words, glued) if g[2] > o[2] + 0.01}
    refs = frozenset((w[0], w[2], w[4]) for w in words if any(abs(w[2] - r) < 0.01 for r in reach))
    inside = [w for w in words if x0 - 1 <= (w[0] + w[2]) / 2 <= x1 + 1 and y0 - 1 <= (w[1] + w[3]) / 2 <= y1 + 1]
    rows = []
    for line in lines_of(inside):
        label, groups = split_line(line, refs)
        rows.append((" ".join(w[4] for w in label), groups, line, is_data(groups)))
    if not any(r[3] for r in rows):
        return []
    value_left = min(g[3] for r in rows if r[3] for g in r[1])
    # phrases over the value area, judged by their centre (a header is wider than the figures under it)
    over = lambda r: sum(1 for a, b, _ in phrase_cells([(w[0], w[2], w[4]) for w in r[2]]) if (a + b) / 2 >= value_left - 2)
    # a header line holds only text, years and day numbers ("Other | - | - | 12" is a body row)
    header_like = lambda r: not r[3] and over(r) >= 2 and all(all(YEARISH.match(t) for t in g[2] if any(c.isdigit() for c in t)) for g in r[1] if has_digit(g))
    blocks, cur, seen = [], [], False
    for r in rows:
        if header_like(r) and seen:
            carried = []
            while cur and not cur[-1][3] and over(cur[-1]) >= 1:
                carried.insert(0, cur.pop())
            blocks.append(cur)
            cur, seen = carried, False
        cur.append(r)
        seen = seen or r[3]
    blocks.append(cur)

    def edges(b):
        g = [g for r in b if r[3] for g in r[1] if has_digit(g)]
        return [c[1] for c in columns_by_right_edge(g)] if g else None

    merged: list = []
    for b in blocks:
        e, p = edges(b), edges(merged[-1]) if merged else None
        if p and e and len(p) == len(e) and all(abs(a - c) <= RIGHT_TOL for a, c in zip(p, e)):
            merged[-1] = merged[-1] + b
        else:
            merged.append(b)
    return [t for t in (build_one(b) for b in merged if any(r[3] for r in b)) if t]


def amounts(text: str) -> set:
    """Figures of a text as digit strings, 3+ digits or with a separator ("1,234", "0.89"); shorter numbers are marks and counts."""
    out = set()
    for t in text.replace("|", " ").split():
        d = re.sub(r"\D", "", t)
        if d and (len(d) >= 3 or any(ch in t for ch in ",.")) and not YEARISH.match(t.strip("$")):
            out.add(d)
    return out


def lost_regions(text: str, words: list) -> list:
    """Regions of lost tables, one per run of MIN_LOST_LINES+ printed data lines whose figures are in the page's text but in none of its Markdown tables,
    each grown up and down over table lines; growth stops at a gap over REGION_GAP, a sentence, or a line whose figures a parsed table already has."""
    in_tables = amounts("\n".join(l for l in text.split("\n") if l.startswith("|")))
    in_text = amounts("\n".join(l for l in text.split("\n") if not l.startswith("|")))
    lines = lines_of(words)
    parsed = [split_line(ln) for ln in lines]
    figs = [amounts(" ".join(t for g in groups for t in g[2])) for _, groups in parsed]
    # a line is lost when fewer than half of its figures are in a Markdown table (a small figure can repeat in the table next door) and all are in the text
    lost = [is_data(g) and sum(1 for x in g if has_digit(x)) >= 3 and bool(f) and len(f & in_tables) < 0.5 * len(f) and f <= in_text
            for (_, g), f in zip(parsed, figs)]
    runs, run = [], None
    for i, flag in enumerate(lost + [False]):
        if flag and run is None:
            run = i
        if not flag and run is not None:
            if i - run >= MIN_LOST_LINES:
                runs.append((run, i - 1))
            run = None
    top = lambda k: min(w[1] for w in lines[k])
    bot = lambda k: max(w[3] for w in lines[k])

    def stop(k):
        words_k = [w[4] for w in lines[k]]
        sentence = len(words_k) >= 8 and not parsed[k][1] and words_k[-1][-1:] in ".:"
        return (sentence or len(words_k) >= 20 or (len(words_k) >= 14 and not figs[k])
                or (is_data(parsed[k][1]) and bool(figs[k]) and len(figs[k] & in_tables) >= 0.5 * len(figs[k])))
    regions, taken = [], -1
    for a, b in runs:
        if a <= taken:  # already inside the region grown from the run above
            continue
        while a > taken + 1 and top(a) - bot(a - 1) <= REGION_GAP and not stop(a - 1):
            a -= 1
        while b < len(lines) - 1 and top(b + 1) - bot(b) <= REGION_GAP and not stop(b + 1):
            b += 1
        taken = b
        span = [w for k in range(a, b + 1) for w in lines[k]]
        regions.append((min(w[0] for w in span) - 2, top(a) - 1, max(w[2] for w in span) + 2, bot(b) + 1))
    return regions


def _replace_paragraphs(text: str, region_words: list, region_figs: set, tables: list):
    """The lost cells are the runs of short paragraphs made only of the region's words that hold some of its figures (a heading or a line Docling kept
    can cut them into several runs). When those runs together hold 60 % of the region's figures, the tables take the place of the first run and the
    other runs go; blocks between them stay. None otherwise (the place of the table is not sure: leave the page)."""
    vocab = {t for w in region_words for t in WORD.findall(w[4].lower())}
    blocks = text.split("\n\n")
    ok = [not b.lstrip().startswith(("|", "#")) and 0 < len(b.split()) <= 15 and set(WORD.findall(b.lower())) <= vocab for b in blocks]
    runs, start = [], None
    for i, flag in enumerate(ok + [False]):
        if flag and start is None:
            start = i
        if not flag and start is not None:
            figs = amounts("\n\n".join(blocks[start:i])) & region_figs
            if figs:
                runs.append((start, i, figs))
            start = None
    if not runs or len(set().union(*(r[2] for r in runs))) < 0.6 * len(region_figs):
        return None
    drop = {k for a, b, _ in runs for k in range(a, b)}
    out = []
    for k, block in enumerate(blocks):
        if k == runs[0][0]:
            out.append("\n\n".join("\n".join(t) for t in tables))
        if k not in drop:
            out.append(block)
    return "\n\n".join(out)


# Ý nghĩa: F3. Sửa trang `text` (Markdown trang `number`; `grids` = bảng Docling của trang; `words` = từ PDF của trang) khi bảng bị mất:
#   (a) một ô bảng Markdown giữ từ COLLAPSED_MIN_NUMBERS số (số chiếm từ nửa số từ): khối bảng đó thay bằng bảng dựng lại trong hộp bảng Docling;
#   (b) mỗi chuỗi từ MIN_LOST_LINES dòng dữ liệu in liên tiếp có số nằm trong chữ trang nhưng không ở bảng nào: các chuỗi đoạn ngắn chỉ gồm chữ của vùng thay bằng bảng dựng lại.
#   Đếm vào `counts`: rebuilt_collapsed, rebuilt_lost, rebuild_skip_place (không chắc chỗ thay), rebuild_skip_empty (không dựng được bảng).
# Giữ vì: đo 21/11 trên 24 trang lỗi: parse đúng 13/244 hàng bảng, bảng dựng lại 234.
# Giới hạn: chỉ chữa (không đụng bảng parse đã có); trang không chắc chỗ thay thì giữ nguyên.
def rebuild_lost_tables(text: str, grids: list, words: list, number: int, counts: Counter) -> str:
    if not words:
        return text
    for grid in grids:
        cell = next((t for row in grid for t, _ in row if len([x for x in t.split() if any(c.isdigit() for c in x)]) >= COLLAPSED_MIN_NUMBERS
                     and len([x for x in t.split() if any(c.isdigit() for c in x)]) >= 0.5 * len(t.split())), None)
        region = getattr(grid, "extent", {}).get(number)
        if cell is None or region is None:
            continue
        lines = text.split("\n")
        key = " ".join(cell.split())
        block = next((b for b in table_blocks(lines) if any(" ".join(c.split()) == key for i in b for c in row_cells(lines[i]))), None)
        tables = rebuild(words, region)
        if block is None or not tables:
            counts["rebuild_skip_empty" if not tables else "rebuild_skip_place"] += 1
            continue
        lines[block[0]:block[-1] + 1] = [l for k, t in enumerate(tables) for l in ([""] if k else []) + t]
        text = "\n".join(lines)
        counts["rebuilt_collapsed"] += 1
    for region in lost_regions(text, words):
        tables = rebuild(words, region)
        inside = [w for w in words if region[0] - 1 <= (w[0] + w[2]) / 2 <= region[2] + 1 and region[1] - 1 <= (w[1] + w[3]) / 2 <= region[3] + 1]
        if not tables:
            counts["rebuild_skip_empty"] += 1
            continue
        out = _replace_paragraphs(text, inside, amounts(" ".join(w[4] for w in inside)), tables)
        if out is None:
            counts["rebuild_skip_place"] += 1
            continue
        text = out
        counts["rebuilt_lost"] += 1
    return text
