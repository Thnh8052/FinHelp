"""Load the in-process models before a user needs them: at startup and after an ingestion batch released them for Docling.
The first question then pays no model load (41 s on the first question after a restart, measured 2026-10-28)."""
import asyncio
import time

from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.chunker import bge_m3_token_counter
from app.modules.query_router.intent import _examples_index
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


async def warm_models() -> None:
    # The intent router's examples are encoded once per process: without this the first question after a restart waited for them
    # (13.6 s against 9.2 s for the next one, measured 2026-11-11). One batch on the remote worker; locally only when models preload.
    if settings.INTENT_ROUTER_ENABLED and (settings.REMOTE_GPU_URL or settings.PRELOAD_MODELS):
        try:
            await _examples_index(DenseEmbeddingService().embed_queries)
        except Exception as exc:  # the first question encodes them instead
            logger.warning(f"Intent router warm-up skipped: {type(exc).__name__}: {str(exc)[:120]}")
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
