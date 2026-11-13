"""A search that times out or loses the vector store is sent again a limited number of times, then reported with its own code (no network, no database)."""
import asyncio

import httpx
import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

from app.core.config import settings
from app.core.error_codes import Code
from app.core.exceptions import ServiceUnavailableError
from app.modules.chat.retrieval_step import search_with_retry


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_RETRY_DELAY_SECONDS", 0)


class Flaky:
    """A search that raises `error` for its first `failures` calls, then answers."""

    def __init__(self, error, failures):
        self.error, self.failures, self.calls = error, failures, 0

    async def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return ["chunk"]


async def test_a_timeout_is_tried_again_and_the_second_try_answers():
    search = Flaky(asyncio.TimeoutError("vector search timed out"), failures=1)
    assert await search_with_retry(search) == ["chunk"]
    assert search.calls == 2


@pytest.mark.parametrize("error", [
    asyncio.TimeoutError("slow"),
    ConnectionError("reset"),
    httpx.ConnectTimeout("no route"),
    ResponseHandlingException(httpx.ReadTimeout("slow store")),
])
async def test_a_dropped_store_is_tried_again_then_reported_with_its_own_code(error):
    search = Flaky(error, failures=99)
    with pytest.raises(ServiceUnavailableError) as stop:
        await search_with_retry(search)
    assert stop.value.code == Code.SEARCH_UNAVAILABLE and stop.value.status_code == 503
    assert search.calls == settings.SEARCH_RETRIES + 1  # one try and the retries, not an endless wait


async def test_no_retry_when_the_setting_is_zero(monkeypatch):
    monkeypatch.setattr(settings, "SEARCH_RETRIES", 0)
    search = Flaky(asyncio.TimeoutError(), failures=99)
    with pytest.raises(ServiceUnavailableError):
        await search_with_retry(search)
    assert search.calls == 1


async def test_a_bug_is_not_retried_and_not_hidden():
    search = Flaky(KeyError("chunk_id"), failures=99)
    with pytest.raises(KeyError):
        await search_with_retry(search)
    assert search.calls == 1


async def test_an_error_the_interface_already_explains_passes_through_untouched():
    """The GPU worker client resends once by itself and reports SYSTEM_NOT_READY: another round here would wait for it twice."""
    gone = ServiceUnavailableError(Code.SYSTEM_NOT_READY)
    search = Flaky(gone, failures=99)
    with pytest.raises(ServiceUnavailableError) as stop:
        await search_with_retry(search)
    assert stop.value is gone and search.calls == 1
