"""The kept-alive client of the remote GPU worker: one client per event loop, a broken kept-alive connection is retried once, an error status and a timeout are not."""
import httpx
import pytest

from app.core.config import settings
from app.modules.retrieval import gpu_client

REAL_CLIENT = httpx.AsyncClient  # the class itself: use() replaces httpx.AsyncClient for the module under test


@pytest.fixture(autouse=True)
def worker(monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_GPU_URL", "https://worker.example/")


def use(monkeypatch, handler):
    """Make every client the module creates talk to `handler` instead of the network."""
    gpu_client._clients.clear()
    monkeypatch.setattr(gpu_client.httpx, "AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


async def test_one_client_is_reused_and_the_path_joins_the_worker_url(monkeypatch):
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json={"ok": len(urls)})

    use(monkeypatch, handler)
    assert await gpu_client.post_json("embed", {"texts": ["a"]}) == {"ok": 1}
    assert await gpu_client.post_json("rerank", {"pairs": []}) == {"ok": 2}
    assert urls == ["https://worker.example/embed", "https://worker.example/rerank"] and len(gpu_client._clients) == 1
    await gpu_client.close()
    assert len(gpu_client._clients) == 0


async def test_a_connection_that_broke_while_idle_is_retried_once(monkeypatch):
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("server disconnected", request=request)
        return httpx.Response(200, json={"scores": [0.5]})

    use(monkeypatch, handler)
    assert await gpu_client.post_json("rerank", {"pairs": [["q", "p"]]}) == {"scores": [0.5]} and len(calls) == 2
    calls.clear()

    def always_broken(request):
        calls.append(1)
        raise httpx.ConnectError("no route", request=request)

    use(monkeypatch, always_broken)
    with pytest.raises(httpx.ConnectError):
        await gpu_client.post_json("rerank", {"pairs": []})
    assert len(calls) == 2  # one retry, then the error goes to the caller (which answers 503 or falls back)


async def test_an_error_status_and_a_timeout_are_not_retried(monkeypatch):
    calls = []

    def status(request):
        calls.append(1)
        return httpx.Response(502, text="bad gateway")

    use(monkeypatch, status)
    with pytest.raises(httpx.HTTPStatusError):
        await gpu_client.post_json("embed", {})
    assert len(calls) == 1
    calls.clear()

    def slow(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    use(monkeypatch, slow)
    with pytest.raises(httpx.ReadTimeout):
        await gpu_client.post_json("embed", {})
    assert len(calls) == 1
