"""Glued footnote marks (23/11): a digit mark printed smaller and raised with no space after a number is ONE PDF word for
`page.get_text("words")` ("1007" = "100" at 7 pt + "7" at 4.5 pt, 2.1 pt higher: Siemens consolidated statements p47; "2024" + "1" in an IFRS
column header). Docling already writes "100 7", but F4 could not prove the mark from the glued word. PageEvidence now splits the word at the
span boundary (the PDF's own font size and baseline), so F4 writes "100⁷". Counted 23/11: 17 of 170 documents, 314 marks.
A number at one size, a lowered (subscript) digit, a letter and a mark after a word stay as they are.
"""
from collections import Counter

import fitz

from app.modules.ingestion.postprocess.evidence import PageEvidence
from app.modules.ingestion.postprocess.table_regrid import raise_marks


def glued(host="100", mark="7", mark_size=4.5, rise=2.1, size=7.0):
    """A one-line page: the label "Siemens AG", then `host` at `size` and `mark` right after it with no space, `rise` points higher."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 100), "Siemens AG", fontsize=size)
    page.insert_text((150, 100), host, fontsize=size)
    page.insert_text((150 + fitz.get_text_length(host, fontsize=size), 100 - rise), mark, fontsize=mark_size)
    return doc, page


def texts(page):
    return [w[4] for w in PageEvidence(page).boxes]


def test_a_glued_raised_mark_becomes_its_own_word():
    doc, page = glued()
    assert [w[4] for w in page.get_text("words")] == ["Siemens", "AG", "1007"]  # the PDF word as PyMuPDF gives it
    boxes = PageEvidence(page).boxes
    assert [w[4] for w in boxes] == ["Siemens", "AG", "100", "7"]
    host, mark = boxes[2], boxes[3]
    assert host[2] <= mark[0] + 0.01 and (mark[3] - mark[1]) < 0.8 * (host[3] - host[1])  # the mark keeps its own small box


def test_f4_raises_the_split_mark_in_a_value_cell():
    doc, page = glued()
    counts = Counter()
    out = raise_marks("| | Equity interest |\n|---|---|\n| Siemens AG | 100 7 |", PageEvidence(page).boxes, counts)
    assert "| Siemens AG | 100⁷ |" in out
    assert counts["raised_marks"] == 1


def test_f4_raises_a_split_mark_after_a_year_in_the_header():
    doc, page = glued(host="2024", mark="1")
    out = raise_marks("| | September 30, 2024 1 |\n|---|---|\n| Revenue | 12 |", PageEvidence(page).boxes, Counter())
    assert "| | September 30, 2024¹ |" in out


def test_a_number_printed_at_one_size_stays_one_word():
    doc, page = glued(mark_size=7.0, rise=0.0)
    assert texts(page) == ["Siemens", "AG", "1007"]


def test_a_lowered_digit_is_not_a_footnote_mark():
    doc, page = glued(rise=-1.5)
    assert texts(page) == ["Siemens", "AG", "1007"]


def test_a_glued_letter_and_a_mark_after_a_word_stay_as_they_are():
    doc, page = glued(mark="a")
    assert texts(page) == ["Siemens", "AG", "100a"]
    doc, page = glued(host="Revenue", mark="1")
    assert texts(page) == ["Siemens", "AG", "Revenue1"]
