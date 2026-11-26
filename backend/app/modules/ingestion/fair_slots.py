"""Parse slots shared fairly between chats (O1-b, docs/VERSION_4/ADMIN_INGESTION_PLAN_2026-11-26.md 1).

The remote worker parses REMOTE_PARALLEL_FILES files at a time. With one first-come-first-served queue, a chat uploading 13 files made a 2-page file
of another chat wait 30 minutes (24/11). Here a freed slot goes to the waiting chats in turn (round robin, in the order they started waiting), and the
files of one chat keep their order. The key is the notebook: one notebook is one chat."""
import asyncio
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from typing import AsyncIterator, Deque, Dict


class FairSlots:
    def __init__(self, slots: int):
        self.free = slots
        self.waiting: "OrderedDict[str, Deque[asyncio.Future]]" = OrderedDict()

    def _waiters(self) -> bool:
        return any(not f.done() for q in self.waiting.values() for f in q)

    async def acquire(self, key: str) -> None:
        if self.free > 0 and not self._waiters():
            self.free -= 1
            return
        future = asyncio.get_running_loop().create_future()
        self.waiting.setdefault(key, deque()).append(future)
        try:
            await future
        except asyncio.CancelledError:
            if future.done() and not future.cancelled():  # the slot was handed over just as the wait was cancelled: pass it on
                self.release()
            raise

    def release(self) -> None:
        """Hand the slot to the first waiting file of the next chat in turn, or free it."""
        for key in list(self.waiting):
            queue = self.waiting[key]
            while queue and queue[0].done():  # cancelled waits
                queue.popleft()
            if not queue:
                del self.waiting[key]
                continue
            queue.popleft().set_result(None)
            if queue:
                self.waiting.move_to_end(key)  # this chat waits for its next turn behind the others
            else:
                del self.waiting[key]
            return
        self.free += 1

    @asynccontextmanager
    async def slot(self, key: str) -> AsyncIterator[None]:
        await self.acquire(key)
        try:
            yield
        finally:
            self.release()


def turn_order(waiting_jobs: list) -> Dict[str, int]:
    """document_id -> its place among the waiting files when every slot is handed out in turn between notebooks (as FairSlots does): the
    notebooks by their first waiting file, then one file of each in turn, each notebook's files in their order."""
    by_notebook: "OrderedDict[str, list]" = OrderedDict()
    for job in sorted(waiting_jobs, key=lambda j: j["queued_at"]):
        by_notebook.setdefault(job.get("notebook_id") or job["document_id"], []).append(job["document_id"])
    order, rounds = [], max((len(v) for v in by_notebook.values()), default=0)
    for r in range(rounds):
        order += [docs[r] for docs in by_notebook.values() if r < len(docs)]
    return {doc: n for n, doc in enumerate(order)}
