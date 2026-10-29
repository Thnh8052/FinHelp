"""Load the in-process models before a user needs them: at startup and after an ingestion batch released them for Docling.
The first question then pays no model load (41 s on the first question after a restart, measured 2026-10-28)."""
import time

from app.core.config import settings
from app.core.logging import logger
from app.services.retrieval.embeddings import DenseEmbeddingService
from app.services.retrieval.reranker import QwenRerankerService


async def warm_models() -> None:
    if not settings.PRELOAD_MODELS:
        return
    t0 = time.perf_counter()
    try:
        await DenseEmbeddingService().embed_queries(["warm up"])
        if settings.RERANK_ENABLED:
            await QwenRerankerService().score_pairs([("warm up", "warm up")])
        logger.info(f"Models warm (embedding + reranker) in {time.perf_counter() - t0:.1f}s")
    except Exception as exc:  # a cold first question is better than a failed startup
        logger.warning(f"Model warm-up skipped: {type(exc).__name__}: {str(exc)[:120]}")
