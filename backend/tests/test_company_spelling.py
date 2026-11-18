"""One spelling per company inside a notebook (system test 18/11, B7/D6). The Amazon 2020 10-K prints its name in capitals on the cover
("AMAZON.COM, INC."), the 2018 one does not ("Amazon.com, Inc."): the topic of the conversation then held two companies, and the follow-up
"Còn Amazon thì sao?" was filled as "So sánh doanh thu của AMAZON.COM và Amazon.com năm 2018". The documents of a notebook are read with one
spelling for each company (the same company key), so the chat, its labels and the interface all show the same name. Nothing is written back."""
import asyncio

from app.modules.chat.scope import source_info
from app.modules.documents.document import DocumentMetadata, DocumentRecord
from app.modules.documents.document_repo import DocumentRepository, one_spelling_per_company
from app.modules.query_router.focus import fill_from_focus, focus_view


def _doc(doc_id, company, year):
    return DocumentRecord(document_id=doc_id, notebook_id="nb", file_name=f"{doc_id}.pdf", file_size_bytes=1, file_path=f"pdfs/nb/{doc_id}.pdf",
                          status="ready", metadata=DocumentMetadata(company_name=company, report_type="10-K", fiscal_year=year,
                                                                    years_covered=[year, year - 1, year - 2]))


def _names(docs):
    return [d.metadata.company_name for d in docs]


def test_the_same_company_written_in_capitals_takes_the_written_out_spelling():
    docs = [_doc("a20", "AMAZON.COM, INC.", 2020), _doc("c20", "Costco Wholesale Corporation", 2020), _doc("a18", "Amazon.com, Inc.", 2018)]
    assert _names(one_spelling_per_company(docs)) == ["Amazon.com, Inc.", "Costco Wholesale Corporation", "Amazon.com, Inc."]


def test_a_company_only_ever_written_in_capitals_is_left_as_it_is():
    docs = [_doc("a20", "AMAZON.COM, INC.", 2020), _doc("a19", "AMAZON.COM, INC.", 2019)]
    assert _names(one_spelling_per_company(docs)) == ["AMAZON.COM, INC.", "AMAZON.COM, INC."]


def test_two_companies_with_close_names_stay_two():
    docs = [_doc("k", "The Coca-Cola Company", 2022), _doc("kc", "COCA-COLA CONSOLIDATED, INC.", 2022)]
    assert _names(one_spelling_per_company(docs)) == ["The Coca-Cola Company", "COCA-COLA CONSOLIDATED, INC."]


def test_the_most_used_written_out_spelling_wins_and_a_missing_name_stays_missing():
    docs = [_doc("x1", "Nike Inc", 2021), _doc("x2", "NIKE, Inc.", 2022), _doc("x3", "NIKE, Inc.", 2020), _doc("n", None, 2020)]
    assert _names(one_spelling_per_company(docs)) == ["NIKE, Inc.", "NIKE, Inc.", "NIKE, Inc.", None]


def test_the_documents_read_from_the_database_are_not_changed_in_place():
    docs = [_doc("a20", "AMAZON.COM, INC.", 2020), _doc("a18", "Amazon.com, Inc.", 2018)]
    one_spelling_per_company(docs)
    assert docs[0].metadata.company_name == "AMAZON.COM, INC."  # the stored record keeps what the cover says


def test_the_notebook_list_is_read_with_one_spelling():
    class Repo(DocumentRepository):
        def __init__(self):
            pass

        async def find_many(self, query, sort_by=None, **kw):
            return [d.model_dump() for d in (_doc("a20", "AMAZON.COM, INC.", 2020), _doc("a18", "Amazon.com, Inc.", 2018))]

    assert _names(asyncio.run(Repo().get_by_notebook("nb"))) == ["Amazon.com, Inc.", "Amazon.com, Inc."]


def test_the_follow_up_names_amazon_once():
    docs = one_spelling_per_company([_doc("a20", "AMAZON.COM, INC.", 2020), _doc("a18", "Amazon.com, Inc.", 2018), _doc("c20", "Costco Wholesale Corporation", 2020)])
    infos = [source_info(d) for d in docs]
    focus = focus_view({"document_ids": ["a20", "a18"], "fiscal_years": [2018], "metric": "revenue"}, ["a20", "a18", "c20"], infos)
    assert focus.companies == ["Amazon.com, Inc."]
    filled = fill_from_focus("Còn Amazon thì sao?", focus, infos, "vi")
    assert filled is None or ("AMAZON.COM" not in filled and filled.count("Amazon") == 1)
