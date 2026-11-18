"""A question that gives its own formula and asks for the figure is a calculation, not a request to explain a concept (found 18/11/2026 while checking
how user-supplied formulas are handled). "Tính ROE theo định nghĩa ROE = lợi nhuận ròng / vốn chủ sở hữu bình quân" was refused with "I do not explain
general finance concepts": the concept rule saw "định nghĩa" and "ROE" and no company or year. Asking what a term means stays refused."""
import pytest

from app.modules.query_router.input_policy import SourceInfo, decide

COSTCO = [SourceInfo("Costco Wholesale Corporation", "10-K", 2020, None, "Costco | 10-K | FY2020", years_covered=[2020, 2019, 2018])]


@pytest.mark.parametrize("q", [
    "Tính ROE theo định nghĩa ROE = lợi nhuận ròng / vốn chủ sở hữu bình quân.",
    "ROE được định nghĩa là lợi nhuận ròng chia vốn chủ sở hữu. Hãy tính ROE.",
    "Define ROE as net income divided by average equity and compute it.",
    "Calculate the operating margin, defined as operating income / net sales.",
    "Biên lợi nhuận gộp được định nghĩa là (doanh thu thuần − giá vốn) / doanh thu thuần, biên lợi nhuận gộp là bao nhiêu?",
])
def test_a_formula_given_with_a_request_for_the_figure_is_answered(q):
    assert decide(q, COSTCO, 1, [], None, "vi").action != "refuse_concept"


@pytest.mark.parametrize("q", [
    "What is ROE?",
    "ROE là gì?",
    "Công thức tính ROE là gì?",
    "Define EBITDA.",
    "Giải thích biên lợi nhuận hoạt động.",
])
def test_asking_what_a_term_means_is_still_a_concept_question(q):
    assert decide(q, COSTCO, 1, [], None, "vi").action == "refuse_concept"
