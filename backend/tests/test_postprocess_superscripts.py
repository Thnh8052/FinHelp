"""F4 (23/11): a digit footnote mark printed small and raised right after a number is written as superscript digits glued to that number
("53.5 1" -> "53.5¹", Coca-Cola 2017 p60; "5.9 2,3" -> "5.9²,³"), so no reader can take it for more digits (53.51) or a second value.
The proof is the PDF (size and position, the test `glue_superscripts` already uses), never the shape of the text: a full-size "3" after "45"
(an "Age" column) stays as it is. Letter marks "(a)" and symbols "*", "†" are not changed.
"""
from collections import Counter

from app.modules.generation.answer_check.amounts import find_amounts
from app.modules.ingestion.api_readers import clean_ocr
from app.modules.ingestion.postprocess.table_regrid import raise_marks
from app.modules.ingestion.postprocess.tokens import superscript

TABLE = "\n".join(["| | 2017 | 2016 |", "|---|---|---|", "| Net revenues | {a} | {b} |", "", "Revenue grew 53.5 1 in the year."])


def word(x0, x1, text, y0=100.0, y1=108.0):
    return (x0, y0, x1, y1, text, 0, 0, 0)


def page(mark="1", y0=97.5, y1=102.5):
    """PDF words: "53.5" (8 points high) then `mark` 5 points high and raised (y0..y1), then "47.2"."""
    return [word(30.0, 80.0, "Net"), word(82.0, 130.0, "revenues"), word(400.0, 420.0, "53.5"), word(420.5, 424.0, mark, y0, y1), word(480.0, 500.0, "47.2")]


def test_superscript_digits_and_comma_list():
    assert superscript("1") == "¹" and superscript("2,3") == "²,³" and superscript("10") == "¹⁰"


def test_a_small_raised_mark_after_a_number_is_glued_as_a_superscript():
    counts = Counter()
    out = raise_marks(TABLE.format(a="53.5 1", b="47.2"), page(), counts)
    assert "| Net revenues | 53.5¹ | 47.2 |" in out
    assert counts["raised_marks"] == 1


def test_a_mark_list_is_glued_too():
    out = raise_marks(TABLE.format(a="53.5 2,3", b="47.2"), page("2,3"), Counter())
    assert "| Net revenues | 53.5²,³ | 47.2 |" in out


def test_text_outside_tables_is_not_changed():
    out = raise_marks(TABLE.format(a="53.5 1", b="47.2"), page(), Counter())
    assert out.endswith("Revenue grew 53.5 1 in the year.")


def test_a_full_size_digit_after_a_number_stays_apart():
    """An "Age" or count column: the "1" is printed at the size of "53.5", so it is a value, not a mark."""
    out = raise_marks(TABLE.format(a="53.5 1", b="47.2"), page("1", 100.0, 108.0), Counter())
    assert "| Net revenues | 53.5 1 | 47.2 |" in out


def test_letter_marks_and_symbols_are_not_changed():
    for mark in ("(a)", "*"):
        out = raise_marks(TABLE.format(a=f"53.5 {mark}", b="47.2"), page(mark), Counter())
        assert f"| Net revenues | 53.5 {mark} | 47.2 |" in out, mark


def test_chandra_superscript_tags_become_superscript_digits():
    assert clean_ocr("| Subordinated notes <sup>3</sup> | 1,016<sup>2</sup> | 5.9<sup>2,3</sup> |") == "| Subordinated notes³ | 1,016² | 5.9²,³ |"
    assert clean_ocr("| Loans <sup>a</sup> | 12 |") == "| Loans [a] | 12 |"


def test_answer_check_reads_a_number_with_a_superscript_mark():
    """Before F4 the answer check skipped "1,016²" entirely ("²" was taken for a letter glued to the number, like "3M")."""
    assert [a.normalized for a in find_amounts("| Notes | 1,016² | 900 |")] == ["1016", "900"]
    assert [a.normalized for a in find_amounts("Revenue 53.5¹ million and 5.9²,³ percent")] == ["53.5", "5.9"]
