"""One HTTP client for the remote GPU worker (REMOTE_GPU_URL), kept alive between calls.

A question calls the worker three to six times (intent, query vectors, Qwen scores, safety net). With a new client per call each call set up a new TLS connection through
the Cloudflare tunnel: measured 0.55 s a call against 0.26 s on a kept-alive connection (an /embed of one text: 0.57 s against 0.31 s). The client belongs to the event
loop that created it (an httpx.AsyncClient cannot be shared between loops), so there is one per running loop.
"""
import asyncio
import weakref
from typing import Any, Dict

import httpx

from app.core.config import settings

_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = weakref.WeakKeyDictionary()
# A connection the tunnel closed while idle fails on first use; these errors mean "no byte of the answer arrived", so the call (an embedding or a score: no side effect) is sent once more.
_BROKEN_CONNECTION = (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError)


def _client() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        # keepalive_expiry: the default 5 s is shorter than the planner call between two worker calls of one question
        client = _clients[loop] = httpx.AsyncClient(timeout=180.0, limits=httpx.Limits(keepalive_expiry=60.0))
    return client


async def post_json(path: str, payload: Dict[str, Any]) -> Any:
    """The JSON answer of POST {REMOTE_GPU_URL}/{path}. Raises httpx.HTTPError (status, timeout, connection) or ValueError (an answer that is not JSON)."""
    url = f"{settings.REMOTE_GPU_URL.rstrip('/')}/{path}"
    try:
        resp = await _client().post(url, json=payload)
    except _BROKEN_CONNECTION:
        resp = await _client().post(url, json=payload)
    resp.raise_for_status()
    return resp.json()


async def close() -> None:
    """Close the client of the running loop (application shutdown)."""
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.aclose()
