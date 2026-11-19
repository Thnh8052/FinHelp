"""A figure must be printed in the excerpt its citation points at (19/11, after the error-rate check of answer_check: a citation moved to another
company's excerpt got through 42 % of the time, because the company check only reads a sentence that names a company).

Measured before the change (experiments/scripts/system_test_18_11/cited_figures.py) on 770 production-like stored answers and 80 dev chat answers:
reporting every such figure caught 1154/1156 planted moves but reported 11 of 447 answers graded correct (figures the answer computed, printed by chance
in another excerpt); leaving out the figures the answer computes reported none of them and still caught every move of a citation whose clause holds a
figure taken from the reports (786/786)."""
from app.modules.generation.answer_check import review
from app.modules.generation.answer_check.citations import check_citations
from app.modules.generation.answer_check.numbers import check_numbers
from tests.test_validation import AMD, CHUNKS, NV


def wrong(answer, chunks=CHUNKS):
    return [(w["n"], w["figure"]) for w in check_citations(answer, chunks, [AMD, NV])["wrong_figure"]]


def test_a_figure_cited_to_an_excerpt_that_does_not_print_it_is_reported():
    assert wrong("Its revenue was $60,922 million [1].") == [(1, "$60,922")]
    assert wrong("Doanh thu của hãng là 60.922 triệu USD [1].") == [(1, "60.922")]
    assert wrong("AMD revenue was $25,785 million [1] and NVIDIA's $60,922 million [1].") == [(1, "$60,922")]


def test_a_figure_in_one_of_the_excerpts_cited_together_is_right():
    assert wrong("AMD revenue was $25,785 million in 2024 [1]. NVIDIA reported $60,922 million [2].") == []
    assert wrong("Revenues were $25,785 million and $60,922 million [1][2].") == []
    assert wrong("Doanh thu lần lượt là 25.785 và 60.922 triệu USD [1, 2].") == []


def test_a_figure_printed_in_no_excerpt_is_left_to_the_number_check():
    assert wrong("Its revenue was $99,999 million [1].") == []


GROWTH = [{"document_id": "amd", "content": "Net revenue 2024 25,785 2023 22,680"}, {"document_id": "nv", "content": "Gross margin 13.7%; 100 stores"}]


def test_a_figure_the_answer_computes_needs_no_excerpt_of_its_own():
    # 13.7% is the growth of the two figures before it; that another excerpt prints a 13.7% is chance
    assert wrong("AMD revenue grew from 22,680 to 25,785, or 13.7% [1].", GROWTH) == []
    assert wrong("Doanh thu AMD tăng từ 22.680 lên 25.785, tức 13,7% [1].", GROWTH) == []
    assert wrong("Growth = (25,785 − 22,680) / 22,680 × 100 = 13.7% [1].", GROWTH) == []  # 100 is a constant


def test_an_amount_is_explained_by_a_written_calculation_only():
    chunks = [{"document_id": "amd", "content": "Revenue 25,785; cost of sales 22,680"}, {"document_id": "nv", "content": "Gross profit 3,105"}]
    assert wrong("Gross profit = 25,785 − 22,680 = 3,105 [1].", chunks) == []
    assert wrong("Lợi nhuận gộp = 25.785 − 22.680 = 3.105 triệu USD [1].", chunks) == []
    assert wrong("Revenue was 25,785 and cost of sales 22,680; gross profit was 3,105 [1].", chunks) == [(1, "3,105")]


def test_the_review_turns_it_into_a_citation_finding():
    found = review.run_checks("Its revenue was $60,922 million [1].", CHUNKS, [AMD, NV], "en", policy_checks=False)
    assert [(f.check, f.text) for f in found] == [("citation", "[1]")] and "$60,922" in found[0].note
    # kept for the trace and the admin queue, not shown to the user (owner 19/11: the line shows only a wrong written calculation)
    assert review.annotate("Its revenue was $60,922 million [1].", found, "en") == "Its revenue was $60,922 million [1]."


def test_an_accounting_standard_is_not_a_figure():
    assert check_numbers("Revenue is recognized under ASC 606 and Topic 842 [1].", CHUNKS)["checked"] == 0


def test_a_citation_written_before_its_figure_is_read_as_such():
    """Live answer 19/11 (Vietnamese restatement question): "the FY2017 10-K [2] reports 18,434 ..., while the FY2019 10-K [1] reports 18,365":
    the citation names the report before its figure, so 18,434 belongs to [2], not to the [1] after it."""
    assert wrong("NVIDIA's report [2] gives $60,922 million, while AMD's report [1] gives $25,785 million.") == []
    assert wrong("Báo cáo của NVIDIA [2] ghi 60.922 triệu USD, trong khi báo cáo của AMD [1] ghi 25.785 triệu USD.") == []
    assert wrong("Its revenue was $60,922 million [1].") == [(1, "$60,922")]  # no citation before it: still reported


# ---------------------------------------------------------------- looser (owner 19/11: the model rarely cites wrong; report only what is surely wrong)
SAME_REPORT = CHUNKS + [{"chunk_id": "a2", "document_id": "amd", "page": 51, "content": "Net revenue increased 14% in 2024, driven by the Data Center segment."}]


def test_a_figure_from_another_page_of_the_same_report_is_not_reported():
    """4 of the 5 wrong citations of 770 stored answers: a line mixing a table figure and a sentence of the same report, cited once, to the sentence
    ("612.2 ÷ 3,140.5 = 19.5%; reported rate = 19.5% [2]"). The figure is right and in the right report: no warning for a page."""
    assert wrong("AMD revenue grew 14% to $25,785 million in 2024 [3].", SAME_REPORT) == []
    assert wrong("Doanh thu AMD năm 2024 tăng 14% lên 25.785 triệu USD [3].", SAME_REPORT) == []
    assert wrong("2024: 25,785 ÷ 22,680 = 1.137; revenue increased 14% [3].", SAME_REPORT) == []
    assert wrong("Its revenue was $60,922 million [3].", SAME_REPORT) == [(3, "$60,922")]  # another company's figure: still reported
    assert wrong("Doanh thu của hãng là 60.922 triệu USD [3].", SAME_REPORT) == [(3, "60.922")]


def test_without_document_ids_nothing_is_reported():
    """A figure can only be shown to belong to another report when the excerpts say which report they are from."""
    assert wrong("Revenue was 60,922 [1].", [{"content": "Revenue 25,785"}, {"content": "Revenue 60,922"}]) == []
