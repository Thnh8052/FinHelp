"""G3: the documents a question targets, by @file or by code (no model), with defaults instead of blocking questions."""
from app.services.query_router.target_resolver import Filing
from app.services.query_router.target_scope import ScopeDoc, decide_targets


def doc(i, company, fy, ticker=None, form="10-K", end=None, covered=None):
    label = f"{company} | {form} | FY{fy}"
    card = {"entity": company, "aliases": [], "ticker": ticker}
    return ScopeDoc(i, label, card, Filing(i, company, form, fy, None, None, end or f"{fy}-12-28"), covered or [fy, fy - 1])


AMD24 = doc("amd24", "Advanced Micro Devices, Inc.", 2024, "AMD")
AMD25 = doc("amd25", "Advanced Micro Devices, Inc.", 2025, "AMD")
NV25 = doc("nv25", "NVIDIA Corporation", 2025, "NVDA", end="2025-01-26")
INTC25 = doc("intc25", "Intel Corporation", 2025, "INTC")
AAPL25 = doc("aapl25", "Apple Inc.", 2025, "AAPL", end="2025-09-27")
FIVE = [AMD24, AMD25, NV25, INTC25, AAPL25]


def test_clear_comparison_targets_one_file_per_company():
    t = decide_targets("Compare revenue of NVIDIA and AMD in fiscal 2025", FIVE, None, vi=False)
    assert sorted(t.document_ids) == ["amd25", "nv25"] and t.rule == "resolved"
    assert "NVIDIA Corporation | 10-K | FY2025" in t.understood and not t.alternatives


def test_no_year_takes_the_latest_and_says_so_without_blocking():
    t = decide_targets("What was AMD's gross margin?", FIVE, None, vi=True)
    assert t.document_ids == ["amd25"] and t.alternatives == [{"document_id": "amd24", "label": AMD24.label}]
    assert "Giả định" in t.understood and any("tag the right file" in n for n in t.notes)


def test_two_years_of_one_company_take_both_files():
    t = decide_targets("AMD revenue 2025 vs 2024", FIVE, None, vi=False)
    assert sorted(t.document_ids) == ["amd24", "amd25"]


def test_lower_case_and_ticker_match():
    assert decide_targets("doanh thu amd năm 2025", FIVE, None, vi=True).document_ids == ["amd25"]
    assert decide_targets("nvda revenue fy2025", FIVE, None, vi=False).document_ids == ["nv25"]


def test_duplicate_reports_take_the_latest_period_and_list_the_other():
    dup = doc("amd25b", "Advanced Micro Devices, Inc.", 2025, "AMD", end="2026-01-02")
    t = decide_targets("AMD revenue fiscal 2025", [AMD25, dup, NV25], None, vi=False)
    assert t.document_ids == ["amd25b"] and t.alternatives[0]["document_id"] == "amd25"


def test_a_year_only_in_a_later_report_uses_its_comparative_column():
    t = decide_targets("AMD revenue in fiscal 2023", [AMD24, NV25], None, vi=False)
    assert t.document_ids == ["amd24"] and "comparative column" in t.understood


def test_no_company_named_leaves_the_choice_to_the_planner():
    t = decide_targets("Which company had the highest revenue?", FIVE, None, vi=False)
    assert t.document_ids == [] and t.rule == "none" and not t.understood


def test_mentions_win_and_a_conflicting_name_is_answered_not_blocked():
    t = decide_targets("doanh thu NVIDIA năm 2025", FIVE, ["amd25"], vi=True)
    assert t.document_ids == ["amd25"] and t.rule == "mentions"
    assert "NVIDIA" in t.understood and "không có trong file được tag" in t.understood
    assert any("does not cover" in n or "do not cover" in n for n in t.notes) and any("tag the right file" in n for n in t.notes)


def test_mentions_flag_a_year_the_tagged_file_does_not_cover():
    t = decide_targets("revenue in 2019", FIVE, ["amd25"], vi=False)
    assert t.document_ids == ["amd25"] and "FY2019" in t.understood


def test_two_mentions_target_both_without_notes_of_conflict():
    t = decide_targets("compare revenue", FIVE, ["amd25", "nv25"], vi=False)
    assert t.document_ids == ["amd25", "nv25"] and not any("tag the right file" in n for n in t.notes)


def test_a_year_earlier_adds_the_previous_report():
    assert sorted(decide_targets("How much more cash did AMD have at the end of 2025 than a year earlier?", FIVE, None, vi=False).document_ids) == ["amd24", "amd25"]


def test_several_quarter_year_pairs_in_one_question():
    q1 = doc("intc23q1", "Intel Corporation", 2023, "INTC", form="earnings release")
    q1.filing.fiscal_quarter = 1
    s3 = doc("crm23q3", "Salesforce, Inc.", 2023, "CRM", form="10-Q")
    s3.filing.fiscal_quarter = 3
    s2 = doc("crm24q2", "Salesforce, Inc.", 2024, "CRM", form="earnings release")
    s2.filing.fiscal_quarter = 2
    t = decide_targets("Rank Salesforce's fiscal third quarter of 2023, Salesforce's fiscal second quarter of 2024 and Intel's first quarter of 2023",
                       [q1, s3, s2], None, vi=False)
    assert sorted(t.document_ids) == ["crm23q3", "crm24q2", "intc23q1"]


def test_a_named_report_type_is_preferred():
    k8 = doc("mcd8k", "McDonald's Corporation", 2023, form="8-K")
    er = doc("mcder", "McDonald's Corporation", 2023, form="earnings release")
    assert decide_targets("In McDonald's 8-K of August 14, 2023, what was the coupon?", [er, k8], None, vi=False).document_ids == ["mcd8k"]


def test_a_name_no_catalog_carries_turns_on_the_net_for_the_rest():
    rbc = doc("rbc", "Royal Bank of Canada", 2025)
    td = doc("td", "The Toronto-Dominion Bank", 2025)
    t = decide_targets("What was the net margin of RBC and of TD in fiscal 2025?", [rbc, td], None, vi=False)
    assert t.document_ids == ["rbc"] and t.uncertain  # "TD" is no catalog name (no ticker confirmed): the TD report gets the safety net
    assert not decide_targets("Compare revenue of NVIDIA and AMD in fiscal 2025", FIVE, None, vi=False).uncertain


def test_quarter_pairs_of_another_company_invent_no_comparative_assumption():
    q1 = doc("intc", "Intel Corporation", 2023, form="earnings release")
    q1.filing.fiscal_quarter = 1
    s2 = doc("crm", "Salesforce, Inc.", 2024, form="earnings release", covered=[2024, 2023])
    s2.filing.fiscal_quarter = 2
    t = decide_targets("Compare the revenue of Intel in Q1 2023 and Salesforce in Q2 fiscal 2024.", [q1, s2], None, vi=False)
    assert sorted(t.document_ids) == ["crm", "intc"] and "comparative" not in t.understood


def test_capitalised_terms_that_are_no_acronym_do_not_turn_on_the_net():
    k8 = doc("mcd8k", "McDonald's Corporation", 2023, form="8-K")
    assert not decide_targets("In McDonald's 8-K, what was the principal of the Medium-Term Notes?", [k8, AMD25], None, vi=False).uncertain
