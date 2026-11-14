"""The net called after the answer (orchestrator._search_more): only for a partial or not_found first answer, a planner that left documents out, and a net that has not run."""
import pytest

from app.core.config import settings
from app.modules.chat.orchestrator import RAGWorkflowOrchestrator, RetrievalResult
from app.modules.query_router.input_policy import Decision
from app.modules.query_router.planner import PlanItem
from tests.test_validation import AMD, NV, _scope

AMD_CHUNK = {"chunk_id": "a", "document_id": "amd", "page": 50, "content": "Net revenue 2024 25,785 2023 22,680"}
NV_CHUNK = {"chunk_id": "n", "document_id": "nv", "page": 40, "content": "Revenue 2024 60,922 2023 26,974", "score": 0.6, "via": "safety_net"}
OPEN = '<answer_meta>{"status": "%s", "short_answer": "x", "citations": [1]}</answer_meta>'
QUESTION = "Which company had the higher revenue in 2024?"  # names no company: the planner chooses the documents


def answer_with(status, text="AMD revenue was $25,785 million [1]."):
    return f"{text}\n{OPEN % status}"


def orchestrator(monkeypatch, answers, net_chunks=(NV_CHUNK,), timings=None, routing="planner"):
    orch = RAGWorkflowOrchestrator.__new__(RAGWorkflowOrchestrator)
    seen = {"answers": [], "net": []}

    async def no_unlisted(query, scope):
        return []

    async def retrieve(query, notebook_id, scope, forced=None, net_others=False):
        return RetrievalResult(scope, {"amd": AMD.label, "nv": NV.label}, [PlanItem("revenue", ["amd"])], ["revenue"], [dict(AMD_CHUNK)], routing, dict(timings or {}))

    async def answer(query, chunks, notes=None, max_tokens=1200, fallback=True):
        seen["answers"].append([c["chunk_id"] for c in chunks])
        return answers[min(len(seen["answers"]), len(answers)) - 1]

    class Search:
        async def safety_net(self, question, plan_queries, notebook_id, document_ids, exclude, kept_document_ids=None):
            seen["net"].append((plan_queries, list(document_ids), list(exclude), kept_document_ids))
            return [(dict(c), 100) for c in net_chunks]

    monkeypatch.setattr(orch, "find_unlisted", no_unlisted)
    monkeypatch.setattr(orch, "retrieve", retrieve)
    monkeypatch.setattr(orch, "_answer", answer)
    orch.hybrid_search = Search()
    monkeypatch.setattr(settings, "LAZY_NET_ENABLED", True)
    monkeypatch.setattr(settings, "NET_ENABLED", True)
    return orch, seen


async def test_a_partial_answer_sends_the_net_to_the_documents_the_plan_left_out_and_is_written_again(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("partial"), answer_with("answered", "AMD revenue was $25,785 million [1]. NVIDIA reported $60,922 million [2].")])
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert seen["net"] == [(["revenue"], ["nv"], ["a"], None)]  # the plan's queries, the document it skipped, no gate
    assert seen["answers"] == [["a"], ["a", "n"]]  # the second answer sees the first excerpts, then the net's
    assert r["trace"]["lazy_net"]["kept"] == "second" and r["trace"]["lazy_net"]["added"] == 1 and r["trace"]["lazy_net"]["status_after"] == "answered"
    assert "NVIDIA reported" in r["answer"] and r["retrieved_chunks_count"] == 2 and len(r["citations"]) == 2
    assert r["trace"]["retrieved_pages"] == [50, 40] and "lazy_net" in r["trace"]["timings"]


async def test_an_answered_question_never_calls_the_net(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("answered")])
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert seen["net"] == [] and r["trace"]["lazy_net"] is None and len(seen["answers"]) == 1


async def test_a_question_that_names_a_company_does_not_search_the_other_documents(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("not_found")])
    r = await orch._answer_one("What was Advanced Micro Devices' revenue in 2024?", "nb", _scope(), Decision(lang="en"))
    assert seen["net"] == [] and r["trace"]["lazy_net"] is None  # the question is about the named company only


@pytest.mark.parametrize("timings,routing", [({"search_net_open": 1.0}, "planner+net"), ({}, "planner+net")])
async def test_the_net_is_not_called_twice(monkeypatch, timings, routing):
    orch, seen = orchestrator(monkeypatch, [answer_with("partial")], timings=timings, routing=routing)
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert r["trace"]["lazy_net"] is None and seen["net"] == []  # it ran before: the gate opened it (key 1.0), or it ran without a gate (no key, routing ends with net)


async def test_a_net_the_gate_closed_is_called_after_the_answer(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("not_found"), answer_with("answered", "NVIDIA reported $60,922 million [2].")], timings={"search_net_open": 0.0}, routing="planner+net")
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert len(seen["net"]) == 1 and r["trace"]["lazy_net"]["kept"] == "second" and r["trace"]["lazy_net"]["status_before"] == "not_found"


async def test_a_worse_second_answer_is_not_kept(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("partial"), answer_with("not_found", "Not found.")])
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert r["trace"]["lazy_net"]["kept"] == "first" and r["trace"]["lazy_net"]["status_after"] == "not_found"
    assert "25,785" in r["answer"] and r["retrieved_chunks_count"] == 1 and len(r["citations"]) == 1


async def test_a_net_that_finds_nothing_leaves_the_first_answer(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("partial")], net_chunks=())
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert r["trace"]["lazy_net"]["added"] == 0 and r["trace"]["lazy_net"]["kept"] == "first" and len(seen["answers"]) == 1


async def test_the_switch_turns_it_off(monkeypatch):
    orch, seen = orchestrator(monkeypatch, [answer_with("partial")])
    monkeypatch.setattr(settings, "LAZY_NET_ENABLED", False)
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert seen["net"] == [] and r["trace"]["lazy_net"] is None


async def test_the_stream_of_a_lazy_net_keeps_the_first_text_then_checks_and_ends_with_the_second_answer(monkeypatch):
    """What the web app sees: the first answer arrives piece by piece, the stage becomes "checking" while the net searches and the answer is written again (the rewrite is not
    streamed), and the answer returned (the one of the final event) is the second one."""
    from app.modules.chat import events
    from app.modules.chat import orchestrator as orch_mod

    answers = [answer_with("partial", "AMD revenue was $25,785 million [1]."), answer_with("answered", "AMD revenue was $25,785 million [1]. NVIDIA reported $60,922 million [2].")]
    calls = []

    async def generate(question, chunks, notes=None, max_tokens=1500):
        calls.append(len(chunks))
        sink = events.answer_sink()
        raw = answers[len(calls) - 1]
        if sink:
            for piece in raw.split("<answer_meta>")[0].split(" "):
                sink(piece + " ")
        return raw

    orch, seen = orchestrator(monkeypatch, [])
    del orch.__dict__["_answer"]  # the helper's fake _answer goes: the real one runs, with the model call faked
    monkeypatch.setattr(orch_mod, "generate_answer", generate)
    monkeypatch.setattr(settings, "OUTPUT_POLICY_ENABLED", False)
    stream = events.ChatStream()
    events.attach(stream)

    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))

    got = []
    while not stream.queue.empty():
        got.append(stream.queue.get_nowait())
    kinds = [k for k, _ in got]
    assert calls == [1, 2] and "NVIDIA reported" in r["answer"]
    assert [d["name"] for k, d in got if k == "stage"] == ["writing", "checking"]  # no second "writing" stage
    last_delta = len(kinds) - 1 - kinds[::-1].index("delta")
    assert kinds.index("delta") > 0 and last_delta < kinds.index("stage", 1)  # the text first, then the "checking" stage, and nothing streamed after it
    assert "".join(d["text"] for k, d in got if k == "delta").strip() == "AMD revenue was $25,785 million [1]."  # only the first answer was streamed


async def test_a_net_that_cannot_reach_the_store_keeps_the_first_answer(monkeypatch):
    """The check after the answer is an extra: the store timing out there must not turn a written answer into an error."""
    import asyncio

    monkeypatch.setattr(settings, "SEARCH_RETRY_DELAY_SECONDS", 0)
    orch, seen = orchestrator(monkeypatch, [answer_with("partial")])

    async def down(*args, **kwargs):
        raise asyncio.TimeoutError("vector search timed out")

    orch.hybrid_search.safety_net = down
    r = await orch._answer_one(QUESTION, "nb", _scope(), Decision(lang="en"))
    assert "AMD revenue was" in r["answer"] and len(seen["answers"]) == 1  # the first answer stands, no second one was written
    assert r["trace"]["lazy_net"]["search_failed"] is True and r["trace"]["lazy_net"]["kept"] == "first"
