"""Page confidence (plan 25/11 night; owner: "set up a confidence metric to decide the flow"). Each page signal carries the share of the pages it fires on that
were really misread (measured, TRIED); a page is as likely wrong as its strongest signal. At REREAD_AT or more the page is read again; at REPORT_AT or more on
the final text it goes on the user's list (the two messages of the document card, unchanged). Step 1 of the plan changes no behaviour: the same pages are
read again and listed as before (the tests of page_quality and parse_check stay as they are)."""
import fitz

from app.modules.ingestion import page_confidence as pc
from app.modules.ingestion.page_quality import text_signals
from tests.test_page_quality import FLAG_ROWS, FUSED, ONE_FUSED, RIGHT, SWAPPED, TABLE, make_flag_pdf, make_pdf


def _rows(rows):
    return "\n".join(["| | 2025 | 2024 |", "|---|---|---|"] + [f"| {label} | {a} | {b} |" for label, a, b in rows])


ONE_WRONG = _rows(FLAG_ROWS[:5] + [(FLAG_ROWS[5][0], FLAG_ROWS[5][1], "")])  # one labelled row short of a figure: no defect, below FLAG_MIN_WRONG


def test_every_signal_has_a_share_a_kind_and_a_source():
    for name, (p, kind, source) in pc.SIGNALS.items():
        assert 0.0 <= p <= 1.0 and kind in ("tables", "figures", "unread") and source, name
    assert 0 < pc.REREAD_AT < pc.REPORT_AT <= 1


def test_a_page_is_as_likely_wrong_as_its_strongest_signal():
    assert pc.p_wrong(["rows", "table_check"]) == pc.SIGNALS["table_check"][0]
    assert pc.p_wrong([]) == 0.0


def test_the_reread_reason_is_the_first_signal_sure_enough():
    """The reason keeps the order of the signals (it picks the re-read's acceptance gate, page_quality.TABLE_REASONS)."""
    assert pc.reread_reason(["missing", "table_check"]) == "missing"
    assert pc.reread_reason(["scanned_unread"]) == pc.reread_reason(["scanned_read"]) == "scanned"
    assert pc.reread_reason(["rows1"]) == "rows1"  # plan step 2 (B7 part 3, NP-52: 16/40 accepted, 0 worse)
    assert pc.reread_reason([]) is None


def test_only_signals_sure_enough_reach_the_user():
    assert pc.reported(["rows"]) == set()  # read again, never listed (NP-11: about 55 % really misread)
    assert pc.reported(["defect"]) == {"tables"}
    assert pc.reported(["scanned_unread"]) == {"unread"}
    assert pc.reported(["scanned_read"]) == set()  # a scan the OCR step read
    assert pc.reported(["chart_lost", "rows"]) == {"figures"}


def test_text_signals_lists_every_table_signal_of_a_page(tmp_path):
    pdf = make_flag_pdf(tmp_path / "f.pdf")
    with fitz.open(str(pdf)) as doc:
        page = doc[0]
        assert text_signals(page, FUSED) == text_signals(page, FUSED, broad=True) == ["table_check"]
        assert text_signals(page, SWAPPED) == [] and text_signals(page, SWAPPED, broad=True) == ["rows"]
        assert text_signals(page, ONE_FUSED, broad=True) == ["defect"]
        assert text_signals(page, ONE_WRONG, broad=True) == ["rows1"] and text_signals(page, ONE_WRONG) == []
        assert text_signals(page, RIGHT, broad=True) == []


def test_a_page_with_one_wrong_row_is_read_again_but_never_listed(tmp_path):
    """Plan step 2 (= B7 part 3): one labelled printed row not held exactly is 11-22 % really misread (NP-51), too weak for the user's list, enough to
    read the page again; the re-read is taken only with fewer wrong rows, like the other table reasons (NP-52: 16 of 40 taken, about 12 better, 0 worse)."""
    from app.modules.ingestion.page_quality import TABLE_REASONS, bad_pages
    from app.modules.ingestion.parse_check import check_pages
    from tests.test_page_quality import page
    pdf = make_flag_pdf(tmp_path / "r.pdf")
    assert bad_pages(pdf, [page(1, ONE_WRONG)], broad=True) == {1: "rows1"}
    assert bad_pages(pdf, [page(1, ONE_WRONG)]) == {}
    assert "rows1" in TABLE_REASONS
    assert check_pages(pdf, [page(1, ONE_WRONG)])[1] == {"tables": [], "unread": []}


async def test_a_one_wrong_row_page_takes_only_a_re_read_with_fewer_wrong_rows(tmp_path):
    from app.modules.ingestion.page_quality import rescue_pages
    from tests.test_page_quality import page
    pdf = make_flag_pdf(tmp_path / "s.pdf")

    async def better(path, numbers):
        return {1: RIGHT}

    async def same(path, numbers):  # the same row still short of its figure
        return {1: ONE_WRONG.replace("| | 2025 | 2024 |", "| | Year 2025 | Year 2024 |")}

    out, report = await rescue_pages(pdf, [page(1, ONE_WRONG)], better)
    assert report["bad"] == {1: "rows1"} and out[0]["text"] == RIGHT and report["replaced"] == [1]
    out, report = await rescue_pages(pdf, [page(1, ONE_WRONG)], same)
    assert out[0]["text"] == ONE_WRONG and report["rejected"] == {1: "more_wrong_rows"}


def test_text_signals_of_scans_and_of_a_page_short_of_its_figures(tmp_path):
    pdf = make_pdf(tmp_path / "s.pdf", ["scan", "text", "blank"])
    with fitz.open(str(pdf)) as doc:
        assert text_signals(doc[0], "<!-- image -->") == ["scanned_unread"]
        assert text_signals(doc[0], TABLE) == ["scanned_read"]  # the OCR step read it
        assert text_signals(doc[1], "Revenue line") == ["missing"]
        assert text_signals(doc[1], TABLE, broad=True) == []
        assert text_signals(doc[2], "") == []  # a blank page is not a scan
