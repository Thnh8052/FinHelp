"""A year is refused only when no selected report prints it anywhere (24/11, TRIED DV-15; owner: "nếu số đấy không xuất hiện ở đâu trong tài liệu thì
từ chối", then "Làm đi"). Before, the reports' years were only the years heading at least 30 % as many tables as the most frequent one, none after
the period end: Amazon's FY2018 10-K prints net sales for 2014 and 2015 in its five-year table and its debt schedule for 2019-2023, yet "net sales in
2015" and "long-term debt in 2021" were refused (19 of 21 printed values of the trap set). With the year check off, the model said "not there" on
21/21 questions about years no report shows, with no invented figure; the "printed anywhere" rule still refuses those outright when the year
appears nowhere. A report read before 24/11 (no years_printed) keeps the old rule until its years are recomputed."""
from app.modules.chat.scope import source_info
from app.modules.documents.document import DocumentMetadata, DocumentRecord
from app.modules.ingestion.catalog import years_printed
from app.modules.query_router.input_policy import PARTIAL_PERIOD_NOTE, SourceInfo, decide

PRINTED_2018 = list(range(2014, 2024)) + [2027, 2037, 2047, 2057]  # five-year table, schedules, notes due 20xx
A18 = SourceInfo("Amazon.com, Inc.", "10-K", 2018, None, "Amazon.com, Inc. 10-K FY2018", years_covered=[2018, 2017, 2016], years_printed=PRINTED_2018)
A18_OLD = SourceInfo("Amazon.com, Inc.", "10-K", 2018, None, "Amazon.com, Inc. 10-K FY2018", years_covered=[2018, 2017, 2016])


def test_years_printed_reads_every_year_of_the_text_like_the_question_reader():
    pages = {1: "| | 2014 | 2015 | 2016 |\n| Net sales | 88,988 | 107,006 | 135,987 |", 2: "Notes due on August 22, 2047. FY2019 results.",
             3: "Not years: $2019 million, 2019,5 %, 120190, 2019.5"}
    assert years_printed(pages) == [2014, 2015, 2016, 2019, 2047]


def test_a_year_printed_in_a_five_year_table_is_answered():
    for q in ("What were Amazon's net sales in 2015?", "Doanh thu thuần của Amazon năm 2014 là bao nhiêu?"):
        assert decide(q, [A18], 1).action == "proceed", q


def test_a_scheduled_year_is_answered_without_a_schedule_word():
    for q in ("What amount of Amazon's long-term debt falls in 2021?", "Khoản nợ dài hạn của Amazon rơi vào năm 2021 là bao nhiêu?",
              "What is the interest rate on Amazon's 2047 notes?"):
        assert decide(q, [A18], 1).action == "proceed", q


def test_a_year_printed_nowhere_is_still_refused():
    for q in ("What were Amazon's net sales in 2010?", "Doanh thu thuần của Amazon năm 2010 là bao nhiêu?", "What were Amazon's net sales in 2033?"):
        d = decide(q, [A18], 1)
        assert d.action == "period_unavailable", q
    assert "FY2010" in decide("Doanh thu thuần của Amazon năm 2010 là bao nhiêu?", [A18], 1).message


def test_a_printed_year_next_to_one_printed_nowhere_gets_the_partial_note():
    d = decide("What were Amazon's net sales in 2015 and 2010?", [A18], 1)
    assert d.action == "proceed" and PARTIAL_PERIOD_NOTE.format(wanted="FY2010") in d.notes


def test_a_report_read_before_the_field_keeps_the_old_rule():
    assert decide("What were Amazon's net sales in 2015?", [A18_OLD], 1).action == "period_unavailable"


def test_the_backfill_reads_the_years_of_a_report_from_its_stored_chunks():
    from scripts.backfill_years_printed import years_from_chunks
    chunks = [{"page": 17, "content": "| | 2014 | 2015 |\n| Net sales | 88,988 | 107,006 |"}, {"page": 32, "content": "4.050% Notes due on August 22, 2047"},
              {"page": 17, "content": "(in millions, except per share data) 2016"}]
    assert years_from_chunks(chunks) == [2014, 2015, 2016, 2047]


def test_the_chat_scope_passes_the_printed_years_on():
    doc = DocumentRecord(document_id="doc_x", notebook_id="nb_x", file_name="AMAZON_2018_10K.pdf", file_path="x.pdf", file_size_bytes=1,
                         metadata=DocumentMetadata(company_name="Amazon.com, Inc.", fiscal_year=2018, years_covered=[2018, 2017], years_printed=[2014, 2021]))
    assert source_info(doc).years_printed == [2014, 2021]
