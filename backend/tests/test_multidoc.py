"""Unit tests for the multi-document path (no GPU, no network, no database)."""
import json

import pytest

from app.core.config import settings
from app.models.document import DocumentMetadata, DocumentRecord
from app.services.ingestion.doc_header import extract_document_header
from app.services.llm.llm_client import LLMUnavailableError
from app.services.query_router import planner
from app.services.query_router.planner import CatalogEntry
from app.services.rag_workflow import generator, retrieval_step
from app.services.rag_workflow.orchestrator import catalog_entry, document_label
from app.services.retrieval.fusion import round_robin_merge
from app.services.retrieval.qdrant_retriever import QdrantRetriever


# ---------------------------------------------------------------- equal slots
def test_round_robin_gives_every_ranking_a_slot():
    # filing A dominates the first query; filing B must still get its share of the 4 slots
    assert round_robin_merge([["a1", "a2", "a3"], ["b1", "b2"]], 4) == ["a1", "b1", "a2", "b2"]


def test_round_robin_skips_duplicates_and_stops_at_limit():
    assert round_robin_merge([["x", "y"], ["x", "z"]], 3) == ["x", "y", "z"]
    assert round_robin_merge([["x", "y", "z"]], 2) == ["x", "y"]


def test_round_robin_handles_empty_input():
    assert round_robin_merge([], 6) == []
    assert round_robin_merge([[], ["a"]], 6) == ["a"]


# ---------------------------------------------------------------- planner
CATALOG = [
    CatalogEntry("d1", "The Coca-Cola Company", "10-K", "FY2022", "ko.pdf"),
    CatalogEntry("d2", "PepsiCo, Inc", "10-K", "FY2022", "pep.pdf"),
]


def test_parse_plan_drops_unknown_ids_and_blank_queries():
    raw = json.dumps({"plan": [
        {"query": "income statement net revenues", "doc_ids": ["d1", "ghost"]},
        {"query": "  ", "doc_ids": ["d2"]},
        {"query": "balance sheet total assets", "doc_ids": []},
        {"query": "x", "doc_ids": "d1"},
    ]})
    plan = planner.parse_plan(raw, ["d1", "d2"], 8)
    assert [(p.query, p.document_ids) for p in plan] == [
        ("income statement net revenues", ["d1"]), ("balance sheet total assets", []), ("x", [])]


def test_parse_plan_caps_items_and_tolerates_prose_or_garbage():
    raw = "Here you go: " + json.dumps({"plan": [{"query": f"q{i}", "doc_ids": ["d1"]} for i in range(12)]})
    assert len(planner.parse_plan(raw, ["d1"], 8)) == 8
    assert planner.parse_plan("not json", ["d1"], 8) == []
    assert planner.parse_plan(json.dumps({"plan": "oops"}), ["d1"], 8) == []


async def test_plan_multi_doc_validates_and_caches(monkeypatch):
    calls = []

    async def fake_chat(messages, **kwargs):
        calls.append(messages[1]["content"])
        return json.dumps({"plan": [{"query": "net revenues", "doc_ids": ["d1"]}, {"query": "net revenues", "doc_ids": ["d2"]}]})

    planner._cache.clear()
    monkeypatch.setattr(planner, "chat_completion", fake_chat)
    plan = await planner.plan_multi_doc("Which had higher revenue in 2022?", CATALOG)
    assert [p.document_ids for p in plan] == [["d1"], ["d2"]]
    assert "d1 | The Coca-Cola Company | 10-K | FY2022" in calls[0] and "PepsiCo, Inc" in calls[0]
    await planner.plan_multi_doc("Which had higher revenue in 2022?", CATALOG)
    assert len(calls) == 1


async def test_plan_multi_doc_degrades_to_empty_when_llm_down_or_catalog_empty(monkeypatch):
    async def down(messages, **kwargs):
        raise LLMUnavailableError("down")

    planner._cache.clear()
    monkeypatch.setattr(planner, "chat_completion", down)
    assert await planner.plan_multi_doc("q", CATALOG) == []
    assert await planner.plan_multi_doc("q", []) == []


# ---------------------------------------------------------------- retriever filters
def test_payload_filter_accepts_one_id_or_a_list():
    r = QdrantRetriever.__new__(QdrantRetriever)
    one = r.build_payload_filter("nb", "d1").must
    many = r.build_payload_filter("nb", ["d1", "d2"]).must
    none = r.build_payload_filter("nb", None).must
    assert len(none) == 1 and len(one) == 2 and len(many) == 2
    assert one[1].match.value == "d1" and many[1].match.any == ["d1", "d2"]


# ---------------------------------------------------------------- generator context
def test_context_shows_company_label_and_multi_doc_note_only_for_several_filings(monkeypatch):
    chunk = {"document_id": "d1", "page": 5, "content": "Net revenues 43,004", "document_label": "Coca-Cola | 10-K | FY2022"}
    assert "Document: Coca-Cola | 10-K | FY2022 [d1], Page: 5" in generator.build_context([chunk])
    plain = generator.build_context([{"document_id": "d1", "page": 5, "content": "x"}])
    assert "Document: d1, Page: 5" in plain  # unchanged format without a label
    v2_one, v2_many = (generator.build_messages("ctx", "q", multi_doc=m)[0]["content"] for m in (False, True))
    assert v2_one == v2_many and "one or more company financial reports" in v2_one  # v2: one text for one or several filings
    for version in ("v1", "v2_one"):                    # one-filing prompts: the note only for several filings
        monkeypatch.setattr(settings, "GENERATION_PROMPT", version)
        assert "MULTIPLE FILINGS" not in generator.build_messages("ctx", "q")[0]["content"]
        assert "MULTIPLE FILINGS" in generator.build_messages("ctx", "q", multi_doc=True)[0]["content"]
    assert "about one SEC filing" in generator.build_messages("ctx", "q")[0]["content"]  # v2_one keeps the measured wording


def test_document_label_and_catalog_entry_fall_back_to_file_name():
    full = DocumentRecord(document_id="d1", notebook_id="n", file_name="ko.pdf", file_size_bytes=1, file_path="p",
                          metadata=DocumentMetadata(company_name="Coca-Cola", report_type="10-K", fiscal_year=2022))
    bare = DocumentRecord(document_id="d2", notebook_id="n", file_name="mystery.pdf", file_size_bytes=1, file_path="p")
    assert document_label(full) == "Coca-Cola | 10-K | FY2022"
    assert document_label(bare) == "mystery.pdf"
    assert catalog_entry(full).line() == "d1 | Coca-Cola | 10-K | FY2022"
    assert catalog_entry(bare).line() == "d2 | mystery.pdf"
    dated = DocumentRecord(document_id="d3", notebook_id="n", file_name="ulta.pdf", file_size_bytes=1, file_path="p",
                           metadata=DocumentMetadata(company_name="Ulta Beauty", report_type="10-K", fiscal_year=2022,
                                                     period_start="2022-01-30", period_end="2023-01-28", comparable_year=2022))
    assert document_label(dated) == "Ulta Beauty | 10-K | FY2022 (2022-01-30 to 2023-01-28)"


# ---------------------------------------------------------------- header extraction at upload
def test_extract_document_header_reads_company_form_and_year():
    cover = (
        "UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nFORM 10-K\nANNUAL REPORT PURSUANT TO SECTION 13\n"
        "For the fiscal year ended December 31, 2022\nAcme Widgets, Inc.\n(Exact name of registrant as specified in its charter)\n"
        "This Annual Report on Form 10-K describes our business."
    )
    body = "Consolidated Statements of Income\nYear Ended December 31, 2022 2021 2020\nAcme Widgets, Inc. and Subsidiaries\nNet sales 1,000 900 800"
    header = extract_document_header([{"page_number": 2, "text": body}, {"page_number": 1, "text": cover}])
    assert header["company_name"] == "Acme Widgets, Inc"
    assert header["report_type"] == "10-K"
    assert header["fiscal_year"] == 2022 and header["fiscal_quarter"] is None
    assert header["header"] == "Acme Widgets, Inc | 10-K | FY2022"


def test_extract_document_header_returns_nones_for_text_without_signals():
    header = extract_document_header([{"page_number": 1, "text": "lorem ipsum dolor sit amet"}])
    assert header["company_name"] is None and header["fiscal_year"] is None and header["header"] == ""


# ---------------------------------------------------------------- retrieve_multi_doc (fake index, no GPU)
class _FakeEmbedder:
    async def embed_queries(self, queries):
        return [[0.0] for _ in queries]

    async def embed_queries_with_sparse(self, queries):
        return [[0.0] for _ in queries], [{} for _ in queries]


class _FakeRetriever:
    def __init__(self):
        self.calls = []

    async def search_vectors(self, vectors, notebook_id, document_id=None, limit=5, per_vector_documents=None):
        self.calls.append((document_id, limit, per_vector_documents))
        return [[{"chunk_id": c, "score": 1.0 - i / 10} for i, c in enumerate(ids)] for ids in ([["a", "b", "c", "d"], ["x", "y"]])]


class _FakeChunks:
    async def get_chunks_by_ids(self, ids):
        import types
        return [types.SimpleNamespace(chunk_id=i, document_id="d", page=1, section=None, chunk_type="text", content=f"text {i}", concept_ids=[]) for i in ids]

    async def get_sparse_weights(self, ids):
        return {i: ({}, 100) for i in ids}  # indexed before lexical weights: dense order


class _FakeReranker:
    SCORES = [0.1, 0.9, 0.5, 0.3]  # the reranker puts the second candidate of each query first

    async def score(self, question, passages):
        return self.SCORES[: len(passages)]

    async def score_pairs(self, pairs):
        seen, out = {}, []
        for query, _ in pairs:
            out.append(self.SCORES[seen.get(query, 0)])
            seen[query] = seen.get(query, 0) + 1
        return out


def _service(monkeypatch, top_k, rerank_top_n):
    from app.core.config import settings
    from app.services.retrieval.hybrid_search import HybridSearchService

    monkeypatch.setattr(settings, "RETRIEVAL_TOP_K", top_k)
    monkeypatch.setattr(settings, "MULTIDOC_RERANK_TOP_N", rerank_top_n)
    monkeypatch.setattr(settings, "RERANK_ENABLED", True)
    svc = HybridSearchService.__new__(HybridSearchService)
    svc.embedder, svc.retriever, svc.chunk_repo, svc.reranker = _FakeEmbedder(), _FakeRetriever(), _FakeChunks(), _FakeReranker()
    return svc


async def test_retrieve_multi_doc_equal_slots_without_rerank(monkeypatch):
    from app.core.config import settings
    from app.services.query_router.planner import PlanItem

    svc = _service(monkeypatch, top_k=4, rerank_top_n=0)
    plan = [PlanItem("revenue", ["d1"]), PlanItem("revenue", ["d2"])]
    chunks = await svc.retrieve_multi_doc(plan, "nb", ["d1", "d2", "d3"])
    assert [c["chunk_id"] for c in chunks] == ["a", "x", "b", "y", "c", "d"]  # no Qwen scores: whole rankings, round robin
    docs, limit, per_vector = svc.retriever.calls[0]
    assert docs == ["d1", "d2", "d3"] and per_vector == [["d1"], ["d2"]] and limit == settings.MULTIDOC_CANDIDATE_LIMIT


async def test_retrieve_multi_doc_qwen_orders_each_item_and_keeps_chunks_near_its_best(monkeypatch):
    from app.services.query_router.planner import PlanItem

    svc = _service(monkeypatch, top_k=2, rerank_top_n=4)
    chunks = await svc.retrieve_multi_doc([PlanItem("revenue", ["d1"]), PlanItem("assets", ["d2"])], "nb", ["d1", "d2"])
    # item 1 Qwen scores a .1, b .9, c .5, d .3 -> keeps b, c (>= .45); item 2 x .1, y .9 -> keeps y
    assert [c["chunk_id"] for c in chunks] == ["b", "y", "c"]


async def test_retrieve_multi_doc_survives_reranker_failure(monkeypatch):
    from app.services.query_router.planner import PlanItem

    svc = _service(monkeypatch, top_k=2, rerank_top_n=4)

    async def boom(pairs):
        raise RuntimeError("CUDA out of memory")

    svc.reranker.score_pairs = boom
    chunks = await svc.retrieve_multi_doc([PlanItem("revenue", ["d1"]), PlanItem("assets", ["d2"])], "nb", ["d1", "d2"])
    assert [c["chunk_id"] for c in chunks][:2] == ["a", "x"]


def test_hybrid_order_mixes_dense_and_sparse_and_keeps_dense_without_weights(monkeypatch):
    from app.services.retrieval.hybrid_search import hybrid_order

    hits = [{"chunk_id": "a", "score": 0.80}, {"chunk_id": "b", "score": 0.79}, {"chunk_id": "c", "score": 0.10}]
    stats = {"a": ({"1": 0.1}, 10), "b": ({"7": 0.9}, 10), "c": ({}, 10)}
    assert hybrid_order(hits, {"7": 1.0}, stats) == ["b", "a", "c"]  # b shares the query's term, a and b are near in dense
    assert hybrid_order(hits, {"7": 1.0}, {k: ({}, 10) for k in stats}) == ["a", "b", "c"]


def test_allocate_relative_threshold_round_robin_and_token_cap(monkeypatch):
    from app.core.config import settings
    from app.services.retrieval.hybrid_search import allocate

    monkeypatch.setattr(settings, "MULTIDOC_MAX_TOKENS", 250)
    lanes = [(["a", "b", "c"], {"a": 0.9, "b": 0.5, "c": 0.2}), (["x", "y"], {"x": 0.04, "y": 0.01})]
    tokens = {"a": 100, "b": 100, "c": 100, "x": 100, "y": 100}
    assert allocate(lanes, tokens) == ["a", "x"]  # b (>= .45) would pass 250 tokens; y < half of x's .04
    assert allocate(lanes, tokens, limit=3) == ["a", "x", "b"]  # a fixed chunk count, no token cap


# ---------------------------------------------------------------- source selection (user chooses the files, the system never guesses)
def _doc(doc_id, name, **meta):
    return DocumentRecord(document_id=doc_id, notebook_id="nb", file_name=name, file_size_bytes=1, file_path="p",
                          indexing_status="completed", metadata=DocumentMetadata(**meta))


def _orchestrator(docs):
    from app.services.rag_workflow.orchestrator import RAGWorkflowOrchestrator

    class Repo:
        async def get_by_notebook(self, notebook_id):
            return docs

    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    orch.doc_repo = Repo()
    return orch


async def test_several_documents_without_a_selection_are_refused():
    from app.services.rag_workflow.orchestrator import SourceSelectionError

    orch = _orchestrator([_doc("d1", "a.pdf"), _doc("d2", "b.pdf")])
    with pytest.raises(SourceSelectionError):
        await orch.resolve_scope("nb", None)


async def test_no_selection_is_refused_even_with_one_document_and_selection_keeps_order():
    from app.services.rag_workflow.orchestrator import SourceSelectionError

    orch = _orchestrator([_doc("d1", "a.pdf")])
    with pytest.raises(SourceSelectionError):  # the system never guesses the scope (chat is disabled until a source is selected)
        await orch.resolve_scope("nb", None)
    orch = _orchestrator([_doc("d1", "a.pdf"), _doc("d2", "b.pdf"), _doc("d3", "c.pdf")])
    assert [d.document_id for d in await orch.resolve_scope("nb", ["d3", "d1", "d3"])] == ["d3", "d1"]
    assert [d.document_id for d in await orch.resolve_scope("nb", None, "d2")] == ["d2"]  # id of an older client


async def test_unknown_or_unready_selection_is_refused():
    from app.services.rag_workflow.orchestrator import SourceSelectionError

    pending = _doc("d2", "b.pdf")
    pending.indexing_status = "indexing"
    orch = _orchestrator([_doc("d1", "a.pdf"), pending])
    for bad in (["ghost"], ["d1", "d2"]):
        with pytest.raises(SourceSelectionError):
            await orch.resolve_scope("nb", bad)


async def test_retrieve_never_widens_the_selection(monkeypatch):
    from app.services.query_router.planner import PlanItem
    from app.services.rag_workflow import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Coca-Cola", fiscal_year=2022, report_type="10-K"),
            _doc("d2", "b.pdf", company_name="PepsiCo", fiscal_year=2022, report_type="10-K")]
    seen = {}

    async def fake_plan(query, catalog):
        seen["catalog"] = [e.document_id for e in catalog]
        return [PlanItem("net revenues", ["d1"]), PlanItem("net revenues", ["d2"])]

    class FakeChunkRepo:
        async def get_chunks_by_document(self, document_id):
            return []

    class FakeSearch:

        async def prescore(self, *a):

            return None

        chunk_repo = FakeChunkRepo()

        async def retrieve_multi_doc(self, plan, notebook_id, scope_ids):
            seen["scope"] = scope_ids
            seen["plan"] = [(p.query, p.document_ids) for p in plan]
            return [{"document_id": "d1", "page": 3, "content": "x", "chunk_type": "table", "score": 1.0}]

        async def retrieve_research(self, query, sub_queries, notebook_id, document_id):
            seen["fallback_filter"] = document_id
            return []

        async def retrieve_by_content(self, query, notebook_id, ids, year_ids):
            seen["by_content"] = (ids, year_ids)
            return []

    async def no_decompose(q):
        return q, ["k"]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", fake_plan)
    monkeypatch.setattr(retrieval_step, "decompose_query", no_decompose)
    orch = _orchestrator(docs)
    orch.hybrid_search = FakeSearch()
    found = await orch.retrieve("which is larger?", "nb", docs)
    assert seen["catalog"] == ["d1", "d2"] and seen["scope"] == ["d1", "d2"]
    assert found.retrieved[0]["document_label"] == "Coca-Cola | 10-K | FY2022"

    # one selected document: the measured single-filing path, filtered to that document, no planner
    seen.clear()
    await orch.retrieve("q", "nb", docs[:1])
    assert seen == {"fallback_filter": "d1"}

    # planner unavailable: routing without a language model, still only the selected documents
    async def broken_plan(query, catalog):
        return []

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", broken_plan)
    seen.clear()
    found = await orch.retrieve("What was PepsiCo's revenue?", "nb", docs)  # R5: the catalog names PepsiCo
    assert found.routing == "r5" and seen["plan"] == [("What was PepsiCo's revenue?", ["d2"])]
    seen.clear()
    found = await orch.retrieve("which is larger?", "nb", docs)  # nothing named, no first-page words: R4 over the selection
    assert found.routing == "r4" and seen == {"by_content": (["d1", "d2"], [])}


async def test_plan_repaired_by_r5_fb3_adds_named_documents_and_fills_items_without_documents(monkeypatch):
    from app.services.query_router.planner import PlanItem
    from app.services.rag_workflow import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Coca-Cola", fiscal_year=2022, report_type="10-K", period_end="2022-12-31"),
            _doc("d2", "b.pdf", company_name="PepsiCo", fiscal_year=2022, report_type="10-K", period_end="2022-12-31"),
            _doc("d3", "c.pdf", company_name="PepsiCo", fiscal_year=2021, report_type="10-K", period_end="2021-12-25")]
    seen = {}

    class FakeSearch:

        async def prescore(self, *a):

            return None

        async def retrieve_multi_doc(self, plan, notebook_id, scope_ids, limit=None):
            seen["plan"] = [(p.query, p.document_ids) for p in plan]
            return [{"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "x" * 400, "chunk_type": "table", "score": 1.0}]

        async def safety_net(self, question, plan_queries, notebook_id, document_ids, exclude):
            seen["net"] = (plan_queries, document_ids, list(exclude))
            big = {"chunk_id": "n2", "document_id": "d2", "page": 5, "content": "pepsi", "chunk_type": "table", "score": 0.9}
            return [(big, 900), ({**big, "chunk_id": "n3", "document_id": "d3"}, 20000)]  # the second does not fit the token cap

    async def plan_missing_pepsi(query, catalog):
        return [PlanItem("net revenues", ["d1"])]

    q = "Compare Coca-Cola and PepsiCo revenue in 2022"
    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan_missing_pepsi)
    orch = _orchestrator(docs)
    orch.hybrid_search = FakeSearch()
    monkeypatch.setattr(orch_mod.settings, "NET_ENABLED", False)
    await orch.retrieve(q, "nb", docs)
    assert seen["plan"] == [("net revenues", ["d1"]), (q, ["d2"])]  # FB3: PepsiCo 2022 named, not searched
    monkeypatch.setattr(orch_mod.settings, "NET_ENABLED", True)
    found = await orch.retrieve(q, "nb", docs)
    assert seen["plan"] == [("net revenues", ["d1"])]  # the safety net replaces FB3
    assert seen["net"] == (["net revenues"], ["d2", "d3"], ["c1"]) and found.routing == "planner+net"
    assert [c["chunk_id"] for c in found.retrieved] == ["c1", "n2"]

    async def plan_without_documents(query, catalog):
        return [PlanItem("net revenues", [])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan_without_documents)
    await orch.retrieve(q, "nb", docs)
    assert seen["plan"] == [("net revenues", ["d1", "d2"])]  # the R5 documents, not the 2021 filing


async def test_targeted_documents_skip_the_net_and_v1_retries_a_missing_one(monkeypatch):
    from app.services.query_router.planner import PlanItem
    from app.services.rag_workflow import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Coca-Cola", fiscal_year=2022), _doc("d2", "b.pdf", company_name="PepsiCo", fiscal_year=2022),
            _doc("d3", "c.pdf", company_name="Apple", fiscal_year=2022)]
    calls = []

    class FakeSearch:

        async def prescore(self, *a):

            return None

        async def retrieve_multi_doc(self, plan, notebook_id, scope_ids, limit=None):
            calls.append(([p.document_ids for p in plan], list(scope_ids), limit))
            return [] if limit else [{"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "x", "chunk_type": "table", "score": 1.0}]

        async def safety_net(self, *a):
            raise AssertionError("no safety net when the documents are targeted")

    async def plan(query, catalog):
        assert [e.document_id for e in catalog] == ["d1", "d2"]  # the planner only sees the targeted documents
        return [PlanItem("revenue", ["d1"]), PlanItem("revenue", ["d2"])]

    monkeypatch.setattr(retrieval_step, "plan_multi_doc", plan)
    orch = _orchestrator(docs)
    orch.hybrid_search = FakeSearch()
    found = await orch.retrieve("Compare revenue", "nb", docs, forced=["d1", "d2"])
    assert found.routing == "targets_planner" and calls[0][1] == ["d1", "d2"]
    assert calls[1] == ([["d2"]], ["d2"], 3) and found.missing == ["d2"]  # V1: one retry inside d2, still nothing


# ---------------------------------------------------------------- one search per (query, document)
def test_expand_plan_gives_every_document_its_own_search():
    from app.services.query_router.planner import PlanItem, expand_plan

    plan = [PlanItem("net revenue", ["d1", "d2", "d3", "d4"])]
    out = expand_plan(plan, ["d1", "d2", "d3", "d4", "d5"], 8)
    assert [(p.query, p.document_ids) for p in out] == [("net revenue", [d]) for d in ["d1", "d2", "d3", "d4"]]
    # an item naming no document means every selected document
    assert [p.document_ids for p in expand_plan([PlanItem("q", [])], ["a", "b"], 8)] == [["a"], ["b"]]


def test_expand_plan_keeps_the_plan_when_it_would_exceed_the_limit():
    from app.services.query_router.planner import PlanItem, expand_plan

    plan = [PlanItem("a", ["d1", "d2", "d3"]), PlanItem("b", ["d1", "d2", "d3"])]
    assert expand_plan(plan, ["d1", "d2", "d3"], 5) == plan
    assert len(expand_plan(plan, ["d1", "d2", "d3"], 6)) == 6


# ---------------------------------------------------------------- companies outside the selected sources
def test_name_candidates_skip_selected_companies_ordinary_words_and_fiscal_labels():
    cands = planner.name_candidates
    assert cands("Which had higher revenue in FY2022, Coca-Cola or PepsiCo?", CATALOG) == []
    assert cands("Compare Pepsi and Apple revenue in FY2022", CATALOG) == ["Apple"]  # "Pepsi" is part of the selected "PepsiCo"
    assert cands("Công ty nào có doanh thu lớn hơn, Quý 2 năm 2022?", CATALOG) == []
    assert cands("What was AMD's and 3M's EBITDA?", CATALOG) == ["AMD", "3M"]
    assert cands("net income of the company", CATALOG) == []


async def test_unlisted_companies_asks_nothing_when_no_candidate(monkeypatch):
    async def never(messages, **kwargs):
        raise AssertionError("no language-model call expected")

    monkeypatch.setattr(planner, "chat_completion", never)
    assert await planner.unlisted_companies("Which had higher revenue, Coca-Cola or PepsiCo?", CATALOG) == []


async def test_unlisted_companies_uses_the_model_verdict_and_ignores_invented_names(monkeypatch):
    prompts = []

    async def fake_chat(messages, **kwargs):
        prompts.append(messages[0]["content"])
        return json.dumps({"unlisted": ["Apple", "Tesla"]})  # Tesla is not in the question: dropped

    planner._guard_cache.clear()
    monkeypatch.setattr(planner, "chat_completion", fake_chat)
    q = "Is Apple's revenue larger than PepsiCo's?"
    assert await planner.unlisted_companies(q, CATALOG) == ["Apple"]
    assert "PepsiCo, Inc | 10-K | FY2022" in prompts[0] and "Apple" in prompts[0]
    await planner.unlisted_companies(q, CATALOG)
    assert len(prompts) == 1  # cached


async def test_unlisted_companies_lets_a_ticker_of_a_selected_company_through(monkeypatch):
    async def fake_chat(messages, **kwargs):
        return json.dumps({"unlisted": []})  # the model knows KO is Coca-Cola

    planner._guard_cache.clear()
    monkeypatch.setattr(planner, "chat_completion", fake_chat)
    assert await planner.unlisted_companies("What were KO net revenues in 2022?", CATALOG) == []


async def test_unlisted_companies_retries_empty_replies_and_fails_open(monkeypatch):
    replies = iter(["", "", json.dumps({"unlisted": ["Apple"]})])

    async def flaky(messages, **kwargs):
        return next(replies)

    planner._guard_cache.clear()
    monkeypatch.setattr(planner, "chat_completion", flaky)
    assert await planner.unlisted_companies("Apple revenue?", CATALOG) == ["Apple"]  # third attempt answers

    async def silent(messages, **kwargs):
        return ""

    async def down(messages, **kwargs):
        raise LLMUnavailableError("down")

    planner._guard_cache.clear()
    monkeypatch.setattr(planner, "chat_completion", silent)
    assert await planner.unlisted_companies("Apple revenue?", CATALOG) == []
    monkeypatch.setattr(planner, "chat_completion", down)
    assert await planner.unlisted_companies("Apple revenue?", CATALOG) == []


async def test_question_about_a_company_outside_the_selection_is_refused_without_retrieval(monkeypatch):
    from app.services.rag_workflow import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Coca-Cola", fiscal_year=2022, report_type="10-K")]

    async def verdict(question, catalog):
        return ["Apple"]

    class Exploding:

        async def prescore(self, *a):

            return None

        async def retrieve_research(self, *args):
            raise AssertionError("nothing may be retrieved")

    monkeypatch.setattr(orch_mod, "unlisted_companies", verdict)
    orch = _orchestrator(docs)
    orch.hybrid_search = Exploding()
    result = await orch.execute_query("Apple revenue?", "nb", document_ids=["d1"])
    assert result["intent"] == "out_of_scope" and result["citations"] == [] and result["retrieved_chunks_count"] == 0
    assert result["trace"]["unlisted_companies"] == ["Apple"]
    assert "Apple" in result["answer"] and "Coca-Cola | 10-K | FY2022" in result["answer"]


def test_extract_document_header_reads_period_dates_and_comparable_year():
    cover = "FORM 10-K\nANNUAL REPORT PURSUANT TO SECTION 13\nFor the fiscal year ended January 28, 2023\nULTA BEAUTY, INC.\n"
    body = ("fiscal 2022, which ended January 28, 2023. Consolidated Balance Sheets as of January 28, 2023 and January 29, 2022. "
            "Fiscal year ended January 28, 2023 compared to fiscal year ended January 29, 2022. Ulta Beauty, Inc. and subsidiaries.") * 3
    h = extract_document_header([{"page_number": 1, "text": cover}, {"page_number": 2, "text": body}])
    assert h["fiscal_year"] == 2022 and h["period_end"] == "2023-01-28" and h["period_start"] == "2022-01-30"
    assert h["comparable_year"] == 2022


def test_extract_document_header_leaves_period_end_empty_when_the_date_is_not_printed():
    # J&J earnings release: columns "Fourth Quarter - 2022"; the only "ended <date>" is a stray prior-year mention
    text = ("Johnson & Johnson (NYSE: JNJ) today announced results for fourth-quarter 2022. Fourth Quarter - 2022 Fourth Quarter - 2021 "
            "Twelve Months Ended - 2022. Fourth quarter 2022 sales. For the fiscal year ended January 2, 2022, see the Annual Report.")
    h = extract_document_header([{"page_number": 1, "text": text}])
    assert h["report_type"] == "earnings release" and h["fiscal_year"] == 2022 and h["fiscal_quarter"] == 4
    assert h["period_end"] is None


async def test_targeted_question_with_an_unknown_name_nets_the_other_documents(monkeypatch):
    from app.services.rag_workflow import orchestrator as orch_mod

    docs = [_doc("d1", "a.pdf", company_name="Royal Bank of Canada", fiscal_year=2025), _doc("d2", "b.pdf", company_name="The Toronto-Dominion Bank", fiscal_year=2025)]
    seen = {}

    class FakeSearch:

        async def prescore(self, *a):

            return None

        async def retrieve_research(self, query, sub_queries, notebook_id, document_id):
            seen["single"] = document_id
            return [{"chunk_id": "c1", "document_id": "d1", "page": 1, "content": "x", "chunk_type": "table", "score": 1.0}]

        async def safety_net(self, question, plan_queries, notebook_id, document_ids, exclude):
            seen["net"] = document_ids
            return [({"chunk_id": "t1", "document_id": "d2", "page": 9, "content": "td net income", "chunk_type": "table", "score": 0.8}, 100)]

    async def no_decompose(q):
        return q, ["net income revenue"]

    monkeypatch.setattr(retrieval_step, "decompose_query", no_decompose)
    orch = _orchestrator(docs)
    orch.hybrid_search = FakeSearch()
    found = await orch.retrieve("net margin of RBC and of TD", "nb", docs, forced=["d1"], net_others=True)
    assert seen == {"single": "d1", "net": ["d2"]} and found.routing == "targets_single+net"
    assert [c["chunk_id"] for c in found.retrieved] == ["c1", "t1"] and found.retrieved[1]["document_label"].startswith("The Toronto-Dominion Bank")
