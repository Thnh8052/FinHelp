"""TC-1: a figure an answer gives to a year must sit in that year's column of the table it is cited to (P0 case T01). Code only, no model.

The two older checks cannot see this: a figure is only looked for in "any excerpt", and a year is only compared with the years the whole report covers,
so FY2019's report (2017-2019) never makes a year wrong."""
from app.core.config import settings
from app.modules.generation.answer_check.column_years import check_columns
from app.modules.generation.verification import verify
from tests.test_validation import AMD, NV

TAX = {"content": "| Year Ended December 31, | 2019 | 2018 | 2017 |\n|---|---|---|---|\n| Statutory U.S. federal tax rate | 21.0 % | 21.0 % | 35.0 % |\n"
                  "| Tax Reform Act | — | 0.1 | 52.4 |\n| Effective tax rate | 16.7 % | 18.0 % | 82.6 % |", "document_id": "d1", "page": 57}


def wrong(answer, chunks=(TAX,)):
    return [c["problem"] for c in check_columns(answer, list(chunks))]


# ---------------------------------------------------------------- what must be reported
def test_a_figure_given_to_the_wrong_year_is_reported_with_the_column_it_sits_in():
    [p] = wrong("Coca-Cola's FY2019 Tax Reform Act impact on the effective tax rate was 52.4 percentage points [1].")
    assert "52.4" in p and "2017" in p and "2019" in p and "[1]" in p
    assert wrong("Coca-Cola's effective tax rate was 82.6 % in FY2018 [1].")


def test_figures_given_to_their_own_columns_are_not_reported():
    assert not wrong("Coca-Cola's FY2017 Tax Reform Act impact on the effective tax rate was 52.4 percentage points [1].")
    assert not wrong("Coca-Cola's effective tax rate was 16.7 % in FY2019 and 18.0 % in FY2018 [1].")
    assert not wrong("In FY2019 the effective tax rate was 16.7 %, and 18.0 % in FY2018 [1].")


def test_two_figures_with_their_years_swapped_are_both_reported():
    assert len(wrong("The effective tax rate was 18.0 % in FY2019 and 16.7 % in FY2018 [1].")) == 2


def test_a_year_in_a_date_is_not_a_year_the_answer_gives_a_figure_to():
    assert not wrong("For the 13 weeks ended December 31, 2017, the Tax Reform Act impact was 52.4 [1].")


# ---------------------------------------------------------------- what is left alone (the check must not flag every answer about a table)
def test_a_figure_printed_in_several_columns_passes_if_one_of_them_is_the_year():
    assert not wrong("The statutory rate was 21.0 % in FY2018 [1].")  # 21.0 is also the 2019 column
    assert not wrong("The statutory rate was 21.0 % in FY2019 [1].")


def test_nothing_is_checked_without_a_year_or_without_a_table():
    assert not wrong("The Tax Reform Act impact was 52.4 [1].")  # no year said
    assert not wrong("The effective tax rate was 52.4 % in FY2019 [1].", [{"content": "The rate was 52.4 % in 2017 after the Act."}])  # no table
    assert not wrong("The effective tax rate was 99.9 % in FY2019 [1].")  # a figure no table prints
    assert not wrong("The effective tax rate was 52.4 % in FY2019 [3].")  # a citation that points at no excerpt


def test_a_figure_that_is_also_in_the_text_of_the_excerpt_is_left_alone():
    chunk = {"content": TAX["content"] + "\n\nThe Act added 52.4 points in fiscal 2019 in a restated view."}
    assert not wrong("The Tax Reform Act impact was 52.4 in FY2019 [1].", [chunk])


def test_a_year_for_a_figure_is_taken_only_when_the_sentence_ties_them_together():
    assert not wrong("Between 2018 and 2019 the rate went from 18.0 % to 16.7 % [1].")  # a range, not "figure in year"
    assert not wrong("In FY2019 the rate was 16.7 %, compared with 82.6 % a year earlier [1].")  # the prior-year figure has no year of its own


def test_each_marker_is_checked_against_its_own_excerpt():
    other = {"content": "| | 2019 | 2018 |\n|---|---|---|\n| Revenue | 52.4 | 10.0 |"}
    assert not wrong("The Act impact was 52.4 in FY2017 [1]. Revenue was 52.4 in FY2019 [2].", [TAX, other])
    assert wrong("Revenue was 52.4 in FY2017 [2].", [TAX, other])  # 52.4 is in the 2017 column of excerpt 1, but this sentence cites excerpt 2


# ---------------------------------------------------------------- how the tables are read
def test_a_header_over_two_rows_is_read():
    chunk = {"content": "| | Year Ended December 31, | | |\n|---|---|---|---|\n| | 2019 | 2018 | 2017 |\n| Revenue | 6,000 | 5,555 | 5,000 |"}
    assert not wrong("Revenue was $5,555 in 2018 [1].", [chunk])
    assert wrong("Revenue was $5,555 in 2019 [1].", [chunk])


def test_a_fiscal_year_that_ends_in_the_next_calendar_year_matches_a_date_header():
    chunk = {"content": "| | January 28, 2023 | January 29, 2022 |\n|---|---|---|\n| Net income | 340,751 | 289,366 |"}
    assert not wrong("Net income was $340,751 thousand in fiscal 2022 [1].", [chunk])  # the year ends in January 2023
    assert not wrong("Net income was $289,366 thousand in fiscal 2021 [1].", [chunk])
    assert wrong("Net income was $289,366 thousand in fiscal 2023 [1].", [chunk])


def test_a_table_whose_columns_cannot_be_lined_up_with_its_header_is_not_used():
    chunk = {"content": "| | 2023 | 2022 |\n|---|---|---|\n| Net sales | 3,226 | 100.0% | 2,729 | 100.0% |"}  # header shorter than the rows
    assert not wrong("Net sales were 2,729 in 2023 [1].", [chunk])


def test_a_percent_column_with_an_empty_header_is_unknown_not_wrong():
    chunk = {"content": "| | 2023 | | 2022 | |\n|---|---|---|---|---|\n| Cost of sales | 2,014 | 62.4% | 1,702 | 62.1% |"}
    assert not wrong("Cost of sales was 62.4 % of sales in 2022 [1].", [chunk])
    assert wrong("Cost of sales was 1,702 in 2023 [1].", [chunk])


# ---------------------------------------------------------------- a table written in the answer itself
def test_an_answer_table_takes_each_cell_year_from_its_own_header():
    table = "| Item | FY2019 | FY2018 |\n|---|---|---|\n| Effective tax rate | 16.7 % [1] | 18.0 % [1] |"
    assert not wrong(table)
    swapped = "| Item | FY2019 | FY2018 |\n|---|---|---|\n| Effective tax rate | 18.0 % [1] | 16.7 % [1] |"
    assert len(wrong(swapped)) == 2


# ---------------------------------------------------------------- inside verify(), where the orchestrator runs it
def test_verify_adds_the_problem_to_the_repair_instructions_when_enabled(monkeypatch):
    docs = [AMD, NV]
    chunks = [{**TAX, "document_id": "amd"}]
    draft = "The Tax Reform Act impact on the effective tax rate was 52.4 percentage points in FY2019 [1]."
    monkeypatch.setattr(settings, "COLUMN_CHECK_ENABLED", True)
    numbers, _, issues = verify(draft, chunks, docs)
    assert numbers["columns"] and any("2017" in i for i in issues)
    monkeypatch.setattr(settings, "COLUMN_CHECK_ENABLED", False)
    numbers, _, issues = verify(draft, chunks, docs)
    assert numbers["columns"] == [] and not any("2017" in i for i in issues)


# ---------------------------------------------------------------- false alarms found on 290 stored answers (each is a sentence the first version wrongly reported)
CAPEX = {"content": "| | 2019 | 2018 | 2017 |\n|---|---|---|---|\n| Capital expenditures | (2,054) | (1,548) | (1,750) |"}


def test_a_list_of_figures_followed_by_a_list_of_years_is_not_guessed():
    assert not wrong("Capital expenditures were $2,054 / $1,548 / $1,750 for 2019/2018/2017 [1].", [CAPEX])
    assert not wrong("Capital expenditures were $2,054, $1,548 and $1,750 in 2019, 2018 and 2017 [1].", [CAPEX])


def test_the_day_of_a_date_is_not_a_figure():
    january = {"content": "| | January 28, 2023 | January 29, 2022 | January 30, 2021 |\n|---|---|---|---|\n| Net sales | 10,208 | 8,630 | 6,152 |\n| Weeks | 52 | 52 | 52 |\n| Day | 28 | 29 | 30 |"}
    assert not wrong("FY2023 is the fiscal year ended January 28, 2023, as labeled in the report [1].", [january])


def test_a_sentence_with_two_years_in_dates_does_not_give_every_figure_the_one_fiscal_year():
    adobe = {"content": "| | November 30, 2018 | December 1, 2017 |\n|---|---|---|\n| Working capital | 555,913 | 3,720,356 |"}
    assert not wrong("In the FY2018 10-K working capital was USD 555,913 thousand at November 30, 2018 and USD 3,720,356 thousand at December 1, 2017 [1].", [adobe])


def test_a_figure_in_billions_or_a_small_decimal_is_not_matched_to_a_cell():
    table = {"content": "| | 2022 | 2021 |\n|---|---|---|\n| Rate | 5.5 | 1.2 |\n| Count | 1.2 | 5.5 |"}
    assert not wrong("The charge was about $1.2 billion in 2022 [1].", [table])
    assert not wrong("The rate was 1.2 in 2022 [1].", [table])


def test_a_figure_taken_from_the_wrong_report_year_is_still_reported():
    """The one real catch on the stored answers: eBay's FY2019 report prints 666 under 2017, an answer gave it to FY2015."""
    ebay = {"content": "| | 2019 | 2018 | 2017 |\n|---|---|---|---|\n| Purchases of property and equipment | (554) | (651) | (666) |"}
    assert wrong("eBay's FY2015 capital expenditure was USD 666 million [1].", [ebay])
