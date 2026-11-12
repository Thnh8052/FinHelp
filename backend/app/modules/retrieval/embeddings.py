import threading
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from app.core.config import settings
from app.core.error_codes import Code
from app.core.exceptions import ServiceUnavailableError
from app.core.logging import logger
from app.modules.retrieval import gpu_client
from app.modules.retrieval.gpu import free_gpu_memory, register_unloader, resolve_device, run_on_gpu

# Measured on the T4 worker with 159 real chunks: 16 takes 5.9-7.2 s against 11-11.7 s for 128, with the same vectors.
REMOTE_DOCUMENT_BATCH = 16


class DenseEmbeddingService:
    """BGE-M3 dense embeddings (1024-d, cosine). One process-wide model, loaded on first use.

    Documents are encoded with max_length 1280 and queries with 512, as in the measured configuration.
    A missing model raises: there is no silent fallback to made-up vectors.
    """

    _model = None
    _load_lock = threading.Lock()

    @classmethod
    def _get_model(cls):
        with cls._load_lock:
            if cls._model is None:
                from FlagEmbedding import BGEM3FlagModel

                device = resolve_device()
                fp16_dir = Path(settings.EMBEDDING_FP16_DIR) if settings.EMBEDDING_FP16_DIR else None
                source = str(fp16_dir) if fp16_dir and (fp16_dir / "model.safetensors").exists() else settings.DEFAULT_EMBEDDING_MODEL
                logger.info(f"Loading embedding model {source} on {device}...")
                cls._model = BGEM3FlagModel(source, use_fp16=device == "cuda", device=device)
            return cls._model

    @classmethod
    def unload(cls) -> None:
        """Free the model (e.g. before a Docling run needs the whole GPU). It reloads lazily on next use."""
        with cls._load_lock:
            cls._model = None
        free_gpu_memory()

    @classmethod
    def _encode(cls, texts: List[str], max_length: int, batch_size: int, sparse: bool = False):
        out = cls._get_model().encode(
            texts,
            batch_size=batch_size,
            max_length=max_length,
            return_dense=True,
            return_sparse=sparse,
            return_colbert_vecs=False,
        )
        dense = np.asarray(out["dense_vecs"], dtype=np.float32)
        if not sparse:
            return dense
        return dense, [{str(k): float(v) for k, v in w.items()} for w in out["lexical_weights"]]

    @classmethod
    async def _encode_remote(cls, texts: List[str], max_length: int, batch_size: int, sparse: bool = False):
        import httpx

        try:
            data = await gpu_client.post_json("embed", {"texts": texts, "max_length": max_length, "batch_size": batch_size, "return_sparse": sparse})
            return data["dense"] if not sparse else (data["dense"], data["sparse"])
        except (httpx.HTTPError, ValueError, KeyError) as exc:  # down, timed out, or a tunnel page instead of JSON: no search can run without the vectors
            logger.warning(f"Remote embedding unavailable: {type(exc).__name__}: {str(exc)[:120]}")
            raise ServiceUnavailableError(Code.SYSTEM_NOT_READY) from exc

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if settings.REMOTE_GPU_URL:
            return await self._encode_remote(texts, settings.EMBEDDING_MAX_LENGTH, REMOTE_DOCUMENT_BATCH, False)
        return (await run_on_gpu("embedder", self._encode, texts, settings.EMBEDDING_MAX_LENGTH, 8)).tolist()

    async def embed_documents_with_sparse(self, texts: List[str]) -> Tuple[List[List[float]], List[Dict[str, float]]]:
        """Dense vectors and BGE-M3 lexical weights ({token id: weight}) in one pass: the sparse half of the multi-document hybrid search."""
        if not texts:
            return [], []
        if settings.REMOTE_GPU_URL:
            return await self._encode_remote(texts, settings.EMBEDDING_MAX_LENGTH, REMOTE_DOCUMENT_BATCH, True)
        dense, sparse = await run_on_gpu("embedder", self._encode, texts, settings.EMBEDDING_MAX_LENGTH, 8, True)
        return dense.tolist(), sparse

    async def embed_queries(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if settings.REMOTE_GPU_URL:
            return await self._encode_remote(texts, settings.QUERY_MAX_LENGTH, 128, False)
        return (await run_on_gpu("embedder", self._encode, texts, settings.QUERY_MAX_LENGTH, 16)).tolist()

    async def embed_queries_with_sparse(self, texts: List[str]) -> Tuple[List[List[float]], List[Dict[str, float]]]:
        if not texts:
            return [], []
        if settings.REMOTE_GPU_URL:
            return await self._encode_remote(texts, settings.QUERY_MAX_LENGTH, 128, True)
        dense, sparse = await run_on_gpu("embedder", self._encode, texts, settings.QUERY_MAX_LENGTH, 16, True)
        return dense.tolist(), sparse

    async def get_embedding(self, text: str) -> List[float]:
        """Single-query convenience kept for existing callers."""
        return (await self.embed_queries([text]))[0]


register_unloader("embedder", DenseEmbeddingService.unload)
