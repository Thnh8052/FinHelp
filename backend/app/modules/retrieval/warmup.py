"""Load the in-process models before a user needs them: at startup and after an ingestion batch released them for Docling.
The first question then pays no model load (41 s on the first question after a restart, measured 2026-10-28)."""
import asyncio
import time

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.chunker import bge_m3_token_counter
from app.modules.retrieval.embeddings import DenseEmbeddingService
from app.modules.retrieval.reranker import QwenRerankerService


async def warm_chunk_tokenizer() -> None:
    """Remote GPU only, awaited before the server accepts uploads: files are chunked in parallel there, and two threads importing
    transformers at once failed a file with an ImportError (seen on the first two uploads after a restart)."""
    if not settings.REMOTE_GPU_URL:
        return
    try:
        await asyncio.to_thread(bge_m3_token_counter)
    except Exception as exc:  # the first upload loads it instead
        logger.warning(f"Chunk tokenizer warm-up skipped: {type(exc).__name__}: {str(exc)[:120]}")


async def warm_guard() -> None:
    """One guard call on a fixed harmless message when the server starts (about 0.0001 dollar). The first call after a start was slower than the
    guard's 3 s deadline (behavior check 18/11/2026, E01: 3.01 s, "unchecked"), so the first user message went through without its safety label."""
    if not settings.GUARD_ENABLED:
        return
    from app.modules.query_router import guard

    try:
        verdict = await guard.classify("Hello", [])
        logger.info(f"Guard warm in {verdict.seconds:.1f}s" + (f" ({verdict.error})" if verdict.error else ""))
    except Exception as exc:  # the first message pays it instead
        logger.warning(f"Guard warm-up skipped: {type(exc).__name__}: {str(exc)[:120]}")


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
