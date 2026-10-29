"""A2 after generation: citations point at real excerpts of the right company / period; one repair, then a visible flag."""
from app.models.document import DocumentMetadata, DocumentRecord
from app.services.answer_check.citations import check_citations, problems
from app.services.query_router.input_policy import Decision
from app.services.query_router.target_resolver import Filing
from app.services.query_router.target_scope import ScopeDoc
from app.services.rag_workflow.orchestrator import RAGWorkflowOrchestrator, RetrievalResult
from app.services.rag_workflow.replies import unlisted_message

AMD = ScopeDoc("amd", "AMD | 10-K | FY2024", {"entity": "Advanced Micro Devices, Inc.", "ticker": "AMD"},
               Filing("amd", "Advanced Micro Devices, Inc.", "10-K", 2024), [2024, 2023, 2022])
NV = ScopeDoc("nv", "NVIDIA | 10-K | FY2024", {"entity": "NVIDIA Corporation", "ticker": "NVDA"}, Filing("nv", "NVIDIA Corporation", "10-K", 2024), [2024, 2023])
CHUNKS = [{"chunk_id": "a", "document_id": "amd", "page": 50, "content": "Net revenue 2024 25,785 2023 22,680"},
          {"chunk_id": "n", "document_id": "nv", "page": 40, "content": "Revenue 2024 60,922 2023 26,974"}]


def test_good_citations_pass():
    out = check_citations("AMD revenue was $25,785 million in 2024 [1]. NVIDIA reported $60,922 million [2].", CHUNKS, [AMD, NV])
    assert out == {"invalid": [], "wrong_company": [], "wrong_period": []}


def test_citation_to_no_excerpt_another_company_or_period_is_caught():
    out = check_citations("AMD revenue was $60,922 million [2]. See also [7]. AMD revenue in 2019 was $6.7 billion [1].", CHUNKS, [AMD, NV])
    assert out["invalid"] == [7]
    assert [w["n"] for w in out["wrong_company"]] == [2]
    assert out["wrong_period"][0]["year"] == 2019
    assert len(problems({"unverified": ["$6.7 billion"]}, out)) == 4


def _orchestrator(answers, monkeypatch):
    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    calls = []

    async def no_unlisted(query, scope):
        return []

    async def retrieve(query, notebook_id, scope, forced=None, net_others=False):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, [], [], [dict(c) for c in CHUNKS], "targets_planner")

    async def answer(query, chunks, notes=None, max_tokens=1200):
        calls.append(notes)
        return answers[min(len(calls), len(answers)) - 1]

    monkeypatch.setattr(orch, "find_unlisted", no_unlisted)
    monkeypatch.setattr(orch, "retrieve", retrieve)
    monkeypatch.setattr(orch, "_answer", answer)
    return orch, calls


def _scope():
    return [DocumentRecord(document_id="amd", notebook_id="nb", file_name="a.pdf", file_size_bytes=1, file_path="p", indexing_status="completed",
                           metadata=DocumentMetadata(company_name="Advanced Micro Devices, Inc.", ticker="AMD", fiscal_year=2024, years_covered=[2024, 2023])),
            DocumentRecord(document_id="nv", notebook_id="nb", file_name="n.pdf", file_size_bytes=1, file_path="p", indexing_status="completed",
                           metadata=DocumentMetadata(company_name="NVIDIA Corporation", ticker="NVDA", fiscal_year=2024, years_covered=[2024, 2023]))]


async def test_a_bad_answer_is_repaired_once(monkeypatch):
    orch, calls = _orchestrator(["AMD revenue was $99,999 million [1].", "AMD revenue was $25,785 million [1]."], monkeypatch)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 2 and "$99,999" in calls[1][-1]
    assert r["verification"]["passed"] and r["verification"]["repaired"] and "⚠️" not in r["answer"]
    assert r["verification"]["first_issues"] and "$99,999" in r["verification"]["first_issues"][0]  # why the repair was tried


async def test_what_stays_wrong_is_flagged_not_hidden(monkeypatch):
    orch, calls = _orchestrator(["AMD revenue was $99,999 million [1]."], monkeypatch)
    r = await orch._answer_one("Doanh thu AMD và NVIDIA năm 2024", "nb", _scope(), Decision(lang="vi"))
    assert len(calls) == 2 and not r["verification"]["passed"]
    assert "⚠️ Lưu ý: số chưa kiểm chứng được trong đoạn trích: $99,999" in r["answer"]


async def test_a_clean_answer_costs_no_second_call(monkeypatch):
    orch, calls = _orchestrator(["AMD revenue was $25,785 million in 2024 [1]; NVIDIA $60,922 million [2]."], monkeypatch)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert len(calls) == 1 and r["verification"] == {"passed": True, "repaired": False, "unverified_figures": [], "first_issues": [],
                                                    "citations": {"invalid": [], "wrong_company": [], "wrong_period": []}}
    assert r["understood"].startswith("I understood the question as about")


async def test_citations_say_which_excerpts_the_answer_uses(monkeypatch):
    orch, _ = _orchestrator(["AMD revenue was $25,785 million in 2024 [1]."], monkeypatch)
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"))
    assert [c["cited"] for c in r["citations"]] == [True, False]
    r = await orch._answer_one("Compare AMD and NVIDIA revenue in 2024", "nb", _scope(), Decision(lang="en"), citation_offset=2)
    assert all(c["cited"] is None for c in r["citations"])  # a later part of a multi-question answer: its [n] restart at 1, so unknown


async def test_a_tagged_question_naming_an_unlisted_company_is_answered_for_the_tag(monkeypatch):
    orch, calls = _orchestrator(["AMD revenue was $25,785 million in 2024 [1]."], monkeypatch)

    async def nvidia(query, scope):
        return ["NVIDIA"]

    monkeypatch.setattr(orch, "find_unlisted", nvidia)
    r = await orch._answer_one("What was NVIDIA's revenue?", "nb", _scope()[:1], Decision(lang="en"), mentions=["amd"])
    assert r["intent"] == "retrieval_rag" and any("NOT in the selected sources" in n for n in calls[0])
    assert unlisted_message(["NVIDIA"], _scope()[:1], "en").startswith("The question mentions NVIDIA")


def test_each_citation_is_checked_against_the_clause_it_closes():
    two = "Intel revenue was $11,715 million in 2024 [1]; NVIDIA reported $60,922 million for fiscal 2023 [2]."
    assert check_citations(two, CHUNKS, [AMD, NV]) == {"invalid": [], "wrong_company": [], "wrong_period": []}
    swapped = "AMD revenue was $25,785 million [2]; NVIDIA reported $60,922 million [1]."
    assert [w["n"] for w in check_citations(swapped, CHUNKS, [AMD, NV])["wrong_company"]] == [2, 1]
