import threading
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from app.core.config import settings
from app.core.logging import logger
from app.services.retrieval.gpu import free_gpu_memory, register_unloader, resolve_device, run_on_gpu


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

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return (await run_on_gpu("embedder", self._encode, texts, settings.EMBEDDING_MAX_LENGTH, 8)).tolist()

    async def embed_documents_with_sparse(self, texts: List[str]) -> Tuple[List[List[float]], List[Dict[str, float]]]:
        """Dense vectors and BGE-M3 lexical weights ({token id: weight}) in one pass: the sparse half of the multi-document hybrid search."""
        if not texts:
            return [], []
        dense, sparse = await run_on_gpu("embedder", self._encode, texts, settings.EMBEDDING_MAX_LENGTH, 8, True)
        return dense.tolist(), sparse

    async def embed_queries(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return (await run_on_gpu("embedder", self._encode, texts, settings.QUERY_MAX_LENGTH, 16)).tolist()

    async def embed_queries_with_sparse(self, texts: List[str]) -> Tuple[List[List[float]], List[Dict[str, float]]]:
        if not texts:
            return [], []
        dense, sparse = await run_on_gpu("embedder", self._encode, texts, settings.QUERY_MAX_LENGTH, 16, True)
        return dense.tolist(), sparse

    async def get_embedding(self, text: str) -> List[float]:
        """Single-query convenience kept for existing callers."""
        return (await self.embed_queries([text]))[0]


register_unloader("embedder", DenseEmbeddingService.unload)
