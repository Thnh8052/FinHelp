"""One rule decides whether two company names are the same company (catalog_route.company_key). Grouping the selected filings
(input_policy), picking a named company's filing (target_resolver) and checking a citation's company (citations) all use it, so they
cannot disagree. No network, no GPU, no database."""
import pytest

from app.modules.query_router.catalog_route import company_key, names
from app.modules.query_router.input_policy import SourceInfo, decide
from app.modules.query_router.target_resolver import Filing, Target, resolve


@pytest.mark.parametrize("a, b, same", [
    ("NIKE, Inc", "NIKE, Inc. and Subsidiaries", True),  # the statement banner adds "and Subsidiaries"
    ("Corning Incorporated", "Corning Incorporated and Subsidiary Companies", True),
    ("Johnson & Johnson", "Johnson and Johnson", True),
    ("Intelsat S.A.", "Intelsat SA", True),  # a dotted legal form is still a legal form
    ("Royal Dutch Shell N.V.", "Royal Dutch Shell", True),
    ("MGM Resorts International", "MGM Resorts", True),
    ("JPMorgan Chase", "JPMorgan Chase & Co", True),
    ("Best Buy", "BEST BUY CO., INC", True),
    ("Coca-Cola", "THE COCA-COLA COMPANY", True),
    ("Wal-Mart", "Walmart Inc.", True),  # spelling: the words are compared written together
    ("The Coca-Cola Company", "Coca-Cola Consolidated, Inc.", False),  # a longer name is another company, not the same one
    ("Ford Motor Company", "Ford Motor Credit Company LLC", False),
    ("The AES Corporation", "AES Andes S.A.", False),
    ("Wal-Mart Stores, Inc.", "Walmart Inc.", False),  # a renamed company needs its aliases: no text rule can know it
])
def test_one_rule_says_whether_two_names_are_the_same_company(a, b, same):
    assert (company_key(a) == company_key(b)) is same


def test_two_spellings_of_one_company_are_one_company_when_grouping():
    old = SourceInfo("NIKE, Inc", "10-K", 2019, None, "NIKE, Inc | 10-K | FY2019")
    new = SourceInfo("NIKE, Inc. and Subsidiaries", "10-K", 2023, None, "NIKE | 10-K | FY2023")
    # one company: its latest period, not "the latest of each of two companies" (which told the answer to use FY2019 too)
    assert decide("What is Nike's latest revenue?", [old, new], 2, []).assumption == "latest_period=FY2023"


def test_a_longer_name_is_not_taken_for_the_shorter_company():
    filings = [Filing("ko", "The Coca-Cola Company", "10-K", 2022), Filing("coke", "Coca-Cola Consolidated, Inc.", "10-K", 2022)]
    assert resolve([Target("Coca-Cola", 2022)], filings)[0].document_ids == ["ko"]  # was both, then "several filings match"


def test_and_subsidiaries_names_no_company():
    tokens = names({"entity": "Ulta Beauty, Inc. and subsidiaries"})
    assert "ubs" not in tokens and "subsidiaries" not in tokens  # "UBS" and "its subsidiaries" in a sentence are not Ulta
    assert {"ulta", "beauty", "ultabeauty"} <= tokens
