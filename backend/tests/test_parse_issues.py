"""Parse problems reach the user instead of staying silent (owner 23/11; research note docs/VERSION_4/PARSING_SUA_VA_BAO_LOI_2026-11-23.md).
A page whose table rows do not match the PDF text layer (ingestion/parse_check.py) and a scanned page that could not be read are listed on the
document card (`pages_to_check`, `pages_unread`); an excerpt taken from a flagged page says so under its citation (`may_be_misread`). The interface
names no component (black-box rule): it only says which pages to check against the original.
"""
from app.modules.chat.chat import CitationOut
from app.modules.documents.document import DocumentRecord
from app.modules.documents.documents import DocumentOut
from app.modules.generation.citation_generator import CitationGenerator
from app.modules.ingestion.chunker import FinancialChunkerService

CHUNK = {"chunk_id": "c1", "document_id": "d", "page": 34, "content": "| Revenue | 100 | 90 |", "score": 0.9}


def test_chunks_of_a_flagged_page_carry_the_table_check_flag():
    pages = [{"page_number": 1, "text": "Revenue was 100 million."}, {"page_number": 2, "text": "Net income was 20 million.", "table_check": True}]
    chunks = FinancialChunkerService.chunk_document("nb", "d", pages, count_tokens=lambda t: len(t.split()))
    assert [(c.page, c.flags) for c in chunks] == [(1, []), (2, ["table_check"])]


def test_a_citation_from_a_flagged_page_may_be_misread():
    assert CitationGenerator.from_retrieved_chunk({**CHUNK, "flags": ["table_check"]}, 1).may_be_misread is True
    assert CitationGenerator.from_retrieved_chunk({**CHUNK, "flags": ["ocr"]}, 1).may_be_misread is False
    assert CitationGenerator.from_retrieved_chunk(CHUNK, 1).may_be_misread is False


def test_the_interface_citation_keeps_the_flag():
    cite = CitationGenerator.from_retrieved_chunk({**CHUNK, "flags": ["table_check"]}, 1)
    assert CitationOut(**cite.model_dump()).may_be_misread is True


def test_the_document_card_lists_the_pages_to_check_and_the_unread_pages():
    doc = DocumentRecord(document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="p", parsing_engine="docling",
                         parse_issues={"tables": [34, 137], "unread": [6, 7]})
    out = DocumentOut.of(doc)
    assert (out.pages_to_check, out.pages_unread, out.tables_may_be_inaccurate) == ([34, 137], [6, 7], False)
    clean = DocumentOut.of(DocumentRecord(document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="p"))
    assert (clean.pages_to_check, clean.pages_unread) == ([], [])


def test_an_excerpt_from_a_page_whose_picture_could_not_be_read_says_so():
    """Owner 24/11: the citation of an excerpt from a page with an unread picture says "a picture on this page could not be read" (figures.py marks the
    page figure_failed; every chunk of the page gets the flag, the picture's place in the text is not known well enough to pick one)."""
    pages = [{"page_number": 1, "text": "Revenue was 100 million."}, {"page_number": 2, "text": "Revenue by segment <!-- image -->", "figure_failed": True}]
    chunks = FinancialChunkerService.chunk_document("nb", "d", pages, count_tokens=lambda t: len(t.split()))
    assert [(c.page, c.flags) for c in chunks] == [(1, []), (2, ["picture_unread"])]
    cite = CitationGenerator.from_retrieved_chunk({**CHUNK, "flags": ["picture_unread"]}, 1)
    assert (cite.picture_unread, cite.may_be_misread, cite.read_from_image, cite.from_figure) == (True, False, False, False)
    assert CitationOut(**cite.model_dump()).picture_unread is True
    assert CitationGenerator.from_retrieved_chunk(CHUNK, 1).picture_unread is False
    vector = [{"page_number": 3, "text": "Revenue by year <!-- image -->", "chart_unread": True}]  # parse_check: a vector chart's printed values lost
    assert FinancialChunkerService.chunk_document("nb", "d", vector, count_tokens=lambda t: len(t.split()))[0].flags == ["picture_unread"]


def test_the_document_card_lists_the_pages_whose_pictures_could_not_be_read():
    """Owner 24/11: a picture left unread (parse_issues "figures") is listed on the document card too."""
    doc = DocumentRecord(document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="p", parsing_engine="docling",
                         parse_issues={"tables": [], "unread": [], "figures": [12, 13]})
    assert DocumentOut.of(doc).pages_pictures_unread == [12, 13]
    assert DocumentOut.of(DocumentRecord(document_id="d", notebook_id="nb", file_name="r.pdf", file_size_bytes=1, file_path="p")).pages_pictures_unread == []
