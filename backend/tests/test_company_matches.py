"""One matcher for company names: short and misspelled names reach the right filing, ordinary words never force one."""
import pytest

from app.modules.query_router.catalog_route import company_matches, named_docs, r5
from app.modules.query_router.input_policy import SourceInfo, mentioned_sources
from app.modules.query_router.planner import CatalogEntry, name_candidates
from app.modules.query_router.target_resolver import Filing
from app.modules.query_router.target_scope import ScopeDoc, decide_targets


def card(entity, ticker=None, aliases=()):
    return {"entity": entity, "aliases": list(aliases), "ticker": ticker}


def level(question, entity, **kw):
    return company_matches(question, [card(entity, **kw)]).get(0, 0)


@pytest.mark.parametrize("question, entity, expected", [
    ("What was PepsiCo's revenue?", "PepsiCo, Inc.", 1),
    ("General Motors revenue in 2021", "General Motors Company", 1),
    ("Bank of America net interest income", "Bank of America Corporation", 1),
    ("AMD revenue 2022", "Advanced Micro Devices, Inc.", 1),
    ("Johnson and Johnson net earnings", "Johnson & Johnson", 1),
    ("What was JP Morgan's net income?", "JPMorgan Chase & Co.", 2),
    ("Wal-Mart revenue", "Walmart Inc.", 1),
    ("Walmart revenue", "WAL-MART STORES, INC.", 2),
    ("Nike's inventory", "NIKE, Inc.", 1),
    ("What was Pepsi's revenue?", "PepsiCo, Inc.", 3),
    ("doanh thu của Pepsi năm 2022", "PepsiCo, Inc.", 3),
    ("Microsft revenue 2022", "Microsoft Corporation", 4),
    ("Salesfroce revenue", "Salesforce, Inc.", 4),
])
def test_a_written_name_reaches_its_company(question, entity, expected):
    assert level(question, entity) == expected


@pytest.mark.parametrize("question, entity", [
    ("What were general and administrative expenses?", "General Motors Company"),
    ("What was the cost of sales in 2023?", "Costco Wholesale Corporation"),
    ("What were sales in 2023?", "Salesforce, Inc."),
    ("What is the target price range in the guidance?", "Target Corporation"),
    ("What were total home sales?", "Home Depot, Inc."),
    ("What were sales in Canada?", "Air Canada"),
    ("Which intelligent systems were deployed?", "Intelligent Systems Corp"),
    ("American Express revenue", "American Airlines Group Inc."),
    ("Bank of America net interest income", "American Airlines Group Inc."),
    ("National Bank of Canada net income", "Royal Bank of Canada"),
    ("Intel revenue in 2022", "Intelligent Systems Corp"),
    ("Apple revenue in 2022", "Applied Materials, Inc."),
    ("What was Coke's revenue?", "The Coca-Cola Company"),  # a nickname is left to the planner
])
def test_ordinary_words_and_other_companies_force_nothing(question, entity):
    assert level(question, entity) == 0


@pytest.mark.parametrize("question, expected", [("Target's revenue in 2022", 1), ("Revenue of Target in 2022", 1), ("target revenue", 0)])
def test_a_name_that_is_an_ordinary_word_needs_capitals(question, expected):
    assert level(question, "Target Corporation") == expected


def test_tickers_and_former_names():
    assert level("nvda revenue fy2025", "NVIDIA Corporation", ticker="NVDA") == 1
    assert level("the key figures", "KeyCorp", ticker="KEY") == 0 and level("KEY net income", "KeyCorp", ticker="KEY") == 1
    assert level("Rogers Cable subscribers", "Other Name Ltd", aliases=["Rogers Cable Inc."]) == 1


def test_one_letter_off_must_point_at_one_company():
    assert company_matches("Oracel revenue", [card("Oracle Corporation"), card("Netflix, Inc.")]) == {0: 4}
    assert company_matches("Nikee revenue", [card("Nike, Inc."), card("Nikem, Inc.")]) == {}
    assert company_matches("Compare Microsoft and Oracel", [card("Microsoft Corporation"), card("Oracle Corporation")]) == {0: 1, 1: 4}


def test_every_caller_uses_the_same_matcher():
    cards = {"pep": card("PepsiCo, Inc."), "gm": card("General Motors Company")}
    assert named_docs("Pepsi revenue", ["pep", "gm"], cards) == ["pep"]
    assert r5("Pepsi revenue", ["pep", "gm"], cards) == ["pep"]
    assert named_docs("general and administrative expenses", ["pep", "gm"], cards) == []
    sources = [SourceInfo("PepsiCo, Inc."), SourceInfo("Salesforce, Inc."), SourceInfo("Other", ticker="ZZZZ")]
    assert mentioned_sources("How much was Pepsi's revenue?", sources) == {0}
    assert mentioned_sources("What were sales?", sources) == set()
    assert mentioned_sources("ZZZZ revenue", sources) == {2}


def test_a_similar_name_goes_to_the_outside_company_check():
    catalog = [CatalogEntry("d1", "Intelligent Systems Corp", "10-K", "FY2022", "isys.pdf"), CatalogEntry("d2", "PepsiCo, Inc", "10-K", "FY2022", "pep.pdf")]
    assert name_candidates("Compare Intel and Pepsi revenue", catalog) == ["Intel"]
    assert name_candidates("Compare Intelligent Systems and PepsiCo revenue", catalog) == []


def doc(i, company, fy):
    return ScopeDoc(i, f"{company} | 10-K | FY{fy}", card(company), Filing(i, company, "10-K", fy, None, None, f"{fy}-12-28"), [fy, fy - 1])


def test_targets_are_forced_only_by_a_real_name():
    docs = [doc("gm", "General Motors Company", 2022), doc("pep", "PepsiCo, Inc.", 2022), doc("ms", "Microsoft Corporation", 2022)]
    assert decide_targets("What were general and administrative expenses in 2022?", docs, None, vi=False).document_ids == []
    pepsi = decide_targets("What was Pepsi's revenue in 2022?", docs, None, vi=False)
    assert pepsi.document_ids == ["pep"] and not pepsi.uncertain
    typo = decide_targets("Microsft revenue in 2022", docs, None, vi=False)
    assert typo.document_ids == ["ms"] and typo.uncertain  # one letter off: the other documents keep the safety net


@pytest.mark.parametrize("question, forced", [
    ("Compare Pepsi and Coke revenue in FY2022", []),  # the planner knows Coke: it must still see that report
    ("Pepsi vs Coke net income in 2022", []),
    ("So sánh doanh thu của Pepsi với Coke năm 2022", []),
    ("Compare Pepsi and Coca-Cola revenue in FY2022", ["ko", "pep"]),  # both names are recognised
    ("Pepsi revenue and net income in FY2022", ["pep"]),  # "and" alone, no other name
    ("JP Morgan revenue and net income in FY2022", ["jpm"]),  # "JP" and "Morgan" are part of the match
])
def test_a_question_listing_an_unrecognised_name_is_left_to_the_planner(question, forced):
    docs = [doc("pep", "PepsiCo, Inc.", 2022), doc("ko", "The Coca-Cola Company", 2022), doc("jpm", "JPMorgan Chase & Co.", 2022)]
    assert sorted(decide_targets(question, docs, None, vi=False).document_ids) == forced
