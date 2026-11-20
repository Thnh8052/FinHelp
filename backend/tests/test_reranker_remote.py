"""The remote reranker: whatever the worker returns that is not a list of scores (a down worker, an error status, a tunnel page instead of JSON, JSON without
"scores") reaches the caller as one RuntimeError, so every caller answers from the first-stage order instead of failing the question with a 500."""
import httpx
import pytest

from app.core.config import settings
from app.modules.retrieval import gpu_client
from app.modules.retrieval.reranker import QwenRerankerService

REAL_CLIENT = httpx.AsyncClient


@pytest.fixture(autouse=True)
def worker(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "https://worker.example/")


def use(monkeypatch, handler):
    gpu_client._clients.clear()
    monkeypatch.setattr(gpu_client.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


async def test_scores_of_a_working_worker_are_returned(monkeypatch):
    use(monkeypatch, lambda request: httpx.Response(200, json={"scores": [0.9, 0.1]}))
    assert await QwenRerankerService().score_pairs([("q", "a"), ("q", "b")]) == [0.9, 0.1]


@pytest.mark.parametrize("response", [
    httpx.Response(502, text="bad gateway"),
    httpx.Response(200, text="<html>Tunnel error 1033</html>", headers={"content-type": "text/html"}),
    httpx.Response(200, json={"detail": "model not loaded"}),
])
async def test_an_unusable_answer_of_the_worker_is_one_runtime_error(monkeypatch, response):
    use(monkeypatch, lambda request: response)
    with pytest.raises(RuntimeError, match="Remote reranker unavailable"):
        await QwenRerankerService().score_pairs([("q", "a")])
