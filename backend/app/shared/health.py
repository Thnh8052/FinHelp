"""Whether the services the application depends on really answer, measured at the moment of asking."""
import asyncio
import time
from typing import Awaitable, Callable, Dict, Optional

from app.infrastructure.database.mongodb import MongoManager
from app.infrastructure.database.qdrant import QdrantManager

PING_TIMEOUT_SECONDS = 3.0


async def _latency_ms(ping: Callable[[], Awaitable]) -> Optional[float]:
    """How long the service took to answer; None when it failed or did not answer in time."""
    started = time.perf_counter()
    try:
        await asyncio.wait_for(ping(), PING_TIMEOUT_SECONDS)
    except Exception:
        return None
    return round((time.perf_counter() - started) * 1000, 1)


async def check_services() -> Dict[str, Optional[float]]:
    mongodb, qdrant = await asyncio.gather(
        _latency_ms(lambda: MongoManager.db.command("ping")),
        _latency_ms(lambda: QdrantManager.client.get_collections()),
    )
    return {"mongodb": mongodb, "qdrant": qdrant}
