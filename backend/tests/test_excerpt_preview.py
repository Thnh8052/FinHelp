"""The excerpts shown when no answer could be written (outage or cut reply) must be readable: they are what the user checks the figures in by hand.
UI check 17/11/2026: the first 400 characters of a table chunk were its header row and a long "|-----|" line, so the user saw only pipes and dashes, no figure."""
from app.modules.generation.replies import excerpt_preview

TABLE = """#### AMAZON.COM, INC.
#### CONSOLIDATED STATEMENTS OF OPERATIONS

(in millions, except per share data)

|                                                                    | Year Ended December 31, - 2016   | Year Ended December 31, - 2017   | Year Ended December 31, - 2018   |
|--------------------------------------------------------------------|----------------------------------|----------------------------------|----------------------------------|
| Net product sales                                                  | $ 94,665                         | $ 118,573                        | $ 141,915                        |
| Net service sales                                                  | 41,322                           | 59,293                           | 90,972                           |
| Total net sales                                                    | 135,987                          | 177,866                          | 232,887                          |
| Operating expenses:                                                |                                  |                                  |                                  |
| Cost of sales                                                      | 88,265                           | 111,934                          | 139,156                          |
| Fulfillment                                                        | 17,619                           | 25,249                           | 34,027                           |
| Marketing                                                          | 7,233                            | 10,069                           | 13,814                           |
| Technology and content                                             | 16,085                           | 22,620                           | 28,837                           |"""

TEXT = ("We have organized our operations into three segments: North America, International, and AWS. These segments reflect the way the Company "
        "evaluates its business performance and manages its operations. Information on reportable segments and reconciliation to consolidated net "
        "income is as follows. " * 3)


def test_a_table_excerpt_shows_its_title_its_header_and_the_first_rows_with_figures():
    out = excerpt_preview(TABLE)
    assert "AMAZON.COM, INC." in out and "CONSOLIDATED STATEMENTS OF OPERATIONS" in out and "####" not in out
    lines = [l for l in out.splitlines() if l.startswith("|")]
    assert lines[0].startswith("| ") and "Year Ended December 31, - 2018" in lines[0]
    assert set(lines[1].replace("|", "").strip()) <= {"-", " "} and len(lines[1]) < 40  # a short, valid separator, not the long line of dashes
    assert any("Total net sales" in l and "232,887" in l for l in lines)
    assert not any("Operating expenses:" in l for l in lines)  # a row without a figure is skipped
    assert len(lines) <= 2 + 6  # header + separator + at most six rows
    assert all("  " not in l for l in lines)  # cells without their padding


def test_a_text_excerpt_is_cut_at_the_end_of_a_sentence():
    out = excerpt_preview(TEXT)
    assert len(out) <= 400 and out.endswith(".") and out.startswith("We have organized")


def test_a_long_sentence_is_cut_at_a_word_with_an_ellipsis():
    out = excerpt_preview("word " * 200)
    assert len(out) <= 401 and out.endswith("…") and not out.endswith(" …")


def test_a_short_text_is_kept_whole():
    assert excerpt_preview("Net revenue 2024 25,785 2023 22,680") == "Net revenue 2024 25,785 2023 22,680"


async def test_the_outage_reply_shows_the_readable_excerpts(monkeypatch):
    from app.modules.chat import orchestrator as orch_mod
    from app.modules.generation.llm_client import LLMUnavailableError
    from tests.test_not_found_flow import orchestrator

    orch = orchestrator(monkeypatch, [])

    async def down(*a, **k):
        raise LLMUnavailableError("LLM_UNAVAILABLE")

    monkeypatch.setattr(orch_mod, "generate_answer", down)
    reply = await orch._answer("Doanh thu thuần của Amazon năm 2018 là bao nhiêu?", [{"chunk_id": "t", "document_id": "amzn", "page": 37, "content": TABLE}])
    assert "| Total net sales | 135,987 | 177,866 | 232,887 |" in reply and "|------" not in reply and "> |" not in reply
