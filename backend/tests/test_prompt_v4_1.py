"""Prompt v4.1 = v4 with three corrections of places where v4 contradicts itself (docs/Version_3/prompt_v5_proposal.md, RAG_CHECKS_SPEC.md L18-L20).
It is selectable with GENERATION_PROMPT="v4_1"; the default stays "v4" until v4.1 is measured on questions it was not designed with. No model: only the messages.

  L20  a citation [n] in a table header leaves the data cells without one, and the column-year check (TC-1) only reads figures that carry a citation
  L19  "one decimal for percentages and ratios" turns a current ratio of 0.76 into 0.8 and 0.87 into 0.9
  L18  the example cell `52 377 [1]` (space-grouped) contradicts "copy each figure exactly as printed" and is copied into the answers
"""
import re

from app.core.config import Settings, settings
from app.modules.generation.answer_check.column_years import check_columns
from app.modules.generation.generator import (
    LANGUAGE_VI_STRUCTURED,
    QUESTION_EN,
    STRUCTURED_PROMPTS,
    SYSTEM_V4,
    SYSTEM_V4_1,
    build_messages,
    split_answer,
)

VIETNAMESE_LETTERS = "ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
CONTEXT = "--- Excerpt [1] (Document: X, Page: 1) ---\nRevenue 100"


def _changed_lines():
    old, new = SYSTEM_V4.splitlines(), SYSTEM_V4_1.splitlines()
    assert len(old) == len(new), "v4.1 must not add or remove lines of v4"
    return [(a, b) for a, b in zip(old, new) if a != b]


# ------------------------------------------------------------------ the flag
def test_the_default_is_still_v4_and_v4_1_is_a_structured_prompt():
    assert Settings.model_fields["GENERATION_PROMPT"].default == "v4"
    assert "v4_1" in STRUCTURED_PROMPTS  # the answer's <answer_meta> block is read, as for v3 and v4


def test_v4_1_is_built_like_v4_except_for_the_system_text(monkeypatch):
    for question in ("What was Nike's revenue in fiscal 2023?", "Doanh thu của Nike năm 2023 là bao nhiêu?"):
        monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4")
        old = build_messages(CONTEXT, question, notes=["Fiscal year ends in May."])
        monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4_1")
        new = build_messages(CONTEXT, question, notes=["Fiscal year ends in May."])
        assert new[1] == old[1]  # same user message: excerpts, language marker
        assert new[0]["content"] == old[0]["content"].replace(SYSTEM_V4, SYSTEM_V4_1, 1)  # same notes header, same Vietnamese block
    assert LANGUAGE_VI_STRUCTURED in new[0]["content"]  # the last question was Vietnamese
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4_1")
    assert build_messages(CONTEXT, "What was Nike's revenue?")[1]["content"].endswith(f"{QUESTION_EN}What was Nike's revenue?")


def test_v4_1_answers_are_split_like_v4_answers(monkeypatch):
    monkeypatch.setattr(settings, "GENERATION_PROMPT", "v4_1")
    _, meta = split_answer('Revenue was 100 [1].\n<answer_meta>{"status": "partial", "short_answer": "100", "citations": [1]}</answer_meta>')
    assert meta["status"] == "partial"
    _, meta = split_answer("Revenue was 100 [1].")  # a missing block counts as answered, as in v4
    assert meta["status"] == "answered"


# ------------------------------------------------------------------ L20: the citation goes in the cells
def test_no_table_template_of_v4_1_carries_a_citation_in_its_header_and_the_rule_says_so():
    templates = [line for line in SYSTEM_V4_1.splitlines() if line.strip().startswith("`|")]
    assert templates and not [t for t in templates if "[n]" in t]
    assert [t for t in SYSTEM_V4.splitlines() if t.strip().startswith("`|") and "[n]" in t], "the test must be able to fail on v4"
    rule = next(line for line in SYSTEM_V4_1.splitlines() if "Concise headers" in line)
    assert "citation" in rule and "data cell" in rule and "never" in rule.lower()
    assert "Every data cell must contain ONLY the core number or concise entity name and its citation `[n]`" in SYSTEM_V4_1  # the cells keep their [n]


def test_the_column_check_reads_a_table_with_the_citation_in_its_cells_and_not_one_with_it_in_the_header():
    excerpt = {"content": "| Item | 2019 | 2018 | 2017 |\n| --- | --- | --- | --- |\n| Purchases of property | 700 | 680 | 666 |\n", "page": 1, "document_id": "d"}
    header_style = "| Metric | FY2019 [1] | FY2018 [1] |\n| :--- | ---: | ---: |\n| Purchases of property | 666 | 680 |\n"  # what v4 asks for
    cell_style = "| Metric | FY2019 | FY2018 |\n| :--- | ---: | ---: |\n| Purchases of property | 666 [1] | 680 [1] |\n"  # what v4.1 asks for
    assert check_columns(header_style, [excerpt]) == []  # 666 is the 2017 figure under FY2019: nothing is read, nothing is said
    assert [c["figure"] for c in check_columns(cell_style, [excerpt])] == ["666"]


# ------------------------------------------------------------------ L19: ratios keep two decimals
def test_ratios_and_multiples_are_asked_for_with_two_decimals_and_percentages_with_one():
    assert "one decimal place for percentages and ratios" in SYSTEM_V4 and "one decimal for percentages and ratios" in SYSTEM_V4
    assert "for percentages and ratios" not in SYSTEM_V4_1
    rules = [line for line in SYSTEM_V4_1.splitlines() if "decimal" in line]
    assert len(rules) == 2
    for line in rules:
        assert re.search(r"one decimal(?: place)? for percentages", line) and re.search(r"two (?:decimals?|places?)? ?for ratios and multiples", line)
        assert "unless asked otherwise" in line


# ------------------------------------------------------------------ L18: no space-grouped example
def test_the_example_cell_no_longer_shows_a_space_grouped_figure():
    assert "52 377" in SYSTEM_V4  # the contradiction v4 has
    assert not re.search(r"\d \d{3}\b", SYSTEM_V4_1)
    cells = next(line for line in SYSTEM_V4_1.splitlines() if "Clean data cells" in line)
    assert "as the report prints it" in cells or "as printed" in cells
    assert "`PwC [4]`" in cells  # the name example stays: it has no number in it


# ------------------------------------------------------------------ nothing else changed
def test_v4_1_differs_from_v4_in_these_lines_only_and_stays_neutral():
    changed = _changed_lines()
    assert len(changed) == 6  # two header templates, the header rule, the cell rule, two rounding rules
    for old, new in changed:
        assert any(key in old for key in ("[n]", "[1]", "52 377", "decimal")), old  # the second template cites [1] and [2]
    assert not [ch for ch in SYSTEM_V4_1.lower() if ch in VIETNAMESE_LETTERS]  # the shared prompt holds no Vietnamese text
    assert "`*Notes:*` list (translate this label and the table headers into the question's language)" in SYSTEM_V4_1
    assert "<answer_meta>" in SYSTEM_V4_1 and SYSTEM_V4_1.rstrip().endswith("</answer_meta>")
