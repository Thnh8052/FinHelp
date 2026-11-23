"""How parse problems reach the answer (owner-approved plan 24/11, section 1.3, channel C).
- An excerpt from a page whose table may be misread (chunk flag "table_check") makes the answer say, when it uses a figure from it, that the figure should be
  checked against the original page (the note `table_note`).
- When nothing is found and a searched document has pages that could not be read (parse_issues "unread": scans without text, pages the parse did not return),
  code adds one line naming those pages: the user knows the information may be there, and the citation / document card opens them.
"""
import pytest

from app.modules.chat.scope import document_label
from app.modules.generation.replies import CHECK_SOURCES, NO_DATA_ANSWER, unread_note
from app.modules.query_router.input_policy import Decision
from tests.test_not_found_flow import META, answering, orchestrator
from tests.test_validation import CHUNKS, _orchestrator, _scope


async def test_excerpts_from_a_page_whose_table_may_be_misread_are_announced_to_the_answer(monkeypatch):
    orch, calls = _orchestrator(["AMD revenue was $25,785 million in 2024 [1]."], monkeypatch)
    CHUNKS[1]["flags"] = ["table_check"]
    try:
        r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    finally:
        CHUNKS[1].pop("flags")
    assert r["trace"]["table_check_excerpts"] == [2]
    note = next(n for n in calls[0] if "may not have been read accurately" in n)
    assert note == ("Excerpts [2] come from a page whose table may not have been read accurately at upload. When you use a figure from them, "
                    "say in one short sentence that it should be checked against the original page (the citation opens it).")
    clean = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert clean["trace"]["table_check_excerpts"] == []
    assert not any("may not have been read accurately" in n for n in calls[-1])


async def test_excerpts_from_a_page_whose_picture_could_not_be_read_are_announced_to_the_answer(monkeypatch):
    """Owner 24/11 (wording approved): a question about that picture or chart is told its figures could not be read, never estimated."""
    orch, calls = _orchestrator(["AMD revenue was $25,785 million in 2024 [1]."], monkeypatch)
    CHUNKS[1]["flags"] = ["picture_unread"]
    try:
        r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    finally:
        CHUNKS[1].pop("flags")
    assert r["trace"]["picture_unread_excerpts"] == [2]
    note = next(n for n in calls[0] if "whose figures could not be read" in n)
    assert note == ("Excerpts [2] come from a page with a picture or chart whose figures could not be read. If the question asks about that picture or "
                    "chart, say in one short sentence that its figures could not be read and that the original page shows it (the citation opens it); "
                    "do not estimate them.")
    clean = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert clean["trace"]["picture_unread_excerpts"] == []
    assert not any("whose figures could not be read" in n for n in calls[-1])


@pytest.mark.parametrize("flags,expected", [
    (["ocr"], (False, True, False)), (["figure"], (False, False, True)), (["table_check", "ocr"], (True, True, False)), ([], (False, False, False)),
])
def test_citations_carry_what_the_interface_says_under_them(flags, expected):
    """Channel B: a page read from its image (flag "ocr") and figures taken from a chart (flag "figure") get a line under the citation, like a page
    whose table may be misread; the API passes the fields on (CitationOut)."""
    from app.modules.chat.chat import CitationOut
    from app.modules.generation.citation_generator import CitationGenerator
    chunk = {"chunk_id": "a", "document_id": "amd", "page": 3, "content": "Revenue 100", "flags": flags}
    c = CitationGenerator.from_retrieved_chunk(chunk, 1)
    assert (c.may_be_misread, c.read_from_image, c.from_figure) == expected
    out = CitationOut(**c.model_dump())
    assert (out.may_be_misread, out.read_from_image, out.from_figure) == expected


def scope_with_unread(pages):
    scope = _scope()
    scope[0].parse_issues = {"tables": [], "unread": pages}
    return scope


@pytest.mark.parametrize("lang,expected", [
    ("vi", "Lưu ý: trang 6–9, 12 của {label} chưa đọc được chữ, thông tin có thể nằm ở đó."),
    ("en", "Note: pages 6–9, 12 of {label} could not be read, the information may be there."),
])
def test_the_unread_line_names_the_pages_as_runs(lang, expected):
    scope = scope_with_unread([6, 7, 8, 9, 12])
    assert unread_note(scope, lang) == expected.format(label=document_label(scope[0]))
    assert unread_note(_scope(), lang) == ""


@pytest.mark.parametrize("lang,question", [("en", "How many stores did AMD have?"), ("vi", "AMD có bao nhiêu cửa hàng?")])
async def test_a_not_found_answer_names_the_unread_pages_of_the_searched_document(monkeypatch, lang, question):
    orch = answering(monkeypatch, "The excerpts do not show the number of stores.\n" + META % ("not_found", "[]"))
    scope = scope_with_unread([3])
    r = await orch._answer_one(question, "nb", scope, Decision(lang=lang))
    assert r["answer"].rstrip().endswith(unread_note(scope, lang))
    assert CHECK_SOURCES[lang] in r["answer"]


async def test_an_answered_question_gets_no_unread_line(monkeypatch):
    orch = answering(monkeypatch, "AMD net revenue was $25,785 million in 2024 [1].\n" + META % ("answered", "[1]"))
    scope = scope_with_unread([3])
    r = await orch._answer_one("What was AMD's revenue in 2024?", "nb", scope, Decision(lang="en"))
    assert unread_note(scope, "en") not in r["answer"]


async def test_no_excerpt_at_all_also_names_the_unread_pages(monkeypatch):
    orch = orchestrator(monkeypatch, [])
    scope = scope_with_unread([3, 4])
    r = await orch._answer_one("Which company had the higher revenue in 2024?", "nb", scope, Decision(lang="en"))
    assert r["answer"].startswith(NO_DATA_ANSWER["en"]) and r["answer"].rstrip().endswith(unread_note(scope, "en"))
