import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from qdrant_client import AsyncQdrantClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import logger
from app.db.repositories.chunk_repo import ChunkRepository
from app.services.retrieval.embeddings import DenseEmbeddingService
from app.services.query_router.planner import PlanItem, expand_plan
from app.services.retrieval.fusion import fuse_with_rerank, round_robin_merge, rrf_merge
from app.services.retrieval.gpu import memory_report
from app.services.retrieval.qdrant_retriever import QdrantRetriever
from app.services.retrieval.reranker import QwenRerankerService


def _z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-9)


def hybrid_order(hits: Sequence[Dict[str, Any]], query_sparse: Dict[str, float], stats: Dict[str, Tuple[Dict[str, float], int]]) -> List[str]:
    """Chunk ids by 0.7 z(dense) + 0.3 z(sparse) over the search's hits (every chunk of its documents). Chunks indexed without
    lexical weights (before 2026-10-27) leave the dense order."""
    hits = [h for h in hits if h.get("chunk_id")]
    if not hits:
        return []
    ids = [h["chunk_id"] for h in hits]
    dense = np.array([h["score"] for h in hits], dtype=np.float64)
    weights = [stats.get(cid, ({}, 0))[0] for cid in ids]
    if not any(weights):
        return ids
    sparse = np.array([sum(query_sparse.get(t, 0.0) * w for t, w in d.items()) for d in weights])
    w = settings.MULTIDOC_DENSE_WEIGHT
    score = w * _z(dense) + (1 - w) * _z(sparse)
    return [ids[i] for i in np.argsort(-score, kind="stable")]


def allocate(lanes: Sequence[Tuple[List[str], Dict[str, float]]], tokens: Dict[str, int], limit: Optional[int] = None) -> List[str]:
    """rel50t8k: from each search, the chunks scoring >= MULTIDOC_REL_THRESHOLD x its best Qwen score (at least its first chunk;
    a search without Qwen scores offers its whole ranking), merged round robin up to MULTIDOC_MAX_CHUNKS chunks and
    MULTIDOC_MAX_TOKENS tokens (the first chunk always fits). `limit`: that many chunks, no token cap."""
    frac = settings.MULTIDOC_REL_THRESHOLD
    kept = [([c for c in r if c in sc and sc[c] >= frac * max(sc.values())] or r[:1]) if sc else list(r) for r, sc in lanes if r]
    out: List[str] = []
    used = 0
    for cid in round_robin_merge(kept, limit or settings.MULTIDOC_MAX_CHUNKS):
        if limit is None and out and used + tokens.get(cid, 0) > settings.MULTIDOC_MAX_TOKENS:
            break
        out.append(cid)
        used += tokens.get(cid, 0)
    return out


class HybridSearchService:
    """Orchestrates retrieval between the Qdrant vector index and MongoDB chunk storage (source of truth for text)."""

    def __init__(self, db: AsyncIOMotorDatabase, qdrant: AsyncQdrantClient):
        self.chunk_repo = ChunkRepository(db)
        self.retriever = QdrantRetriever(qdrant)
        self.embedder = DenseEmbeddingService()
        self.reranker = QwenRerankerService()
        self._qwen: Dict[Tuple[str, str], float] = {}  # (query, chunk_id) -> P(yes), for this request (one service per request)

    async def _score_cached(self, query: str, chunks: List[Dict[str, Any]]) -> List[float]:
        """Qwen3 P(yes) of each chunk for the query; pairs scored earlier in this request (prescore) are not scored again."""
        todo = [c for c in chunks if (query, c["chunk_id"]) not in self._qwen]
        if todo:
            for c, s in zip(todo, await self.reranker.score(query, [c["content"] for c in todo])):
                self._qwen[(query, c["chunk_id"])] = s
        return [self._qwen[(query, c["chunk_id"])] for c in chunks]

    async def prescore(self, question: str, notebook_id: str, document_id: Optional[str]) -> None:
        """Score the question's first-stage pool while the language model is still writing the sub-queries (the GPU is idle then):
        the final pool is mostly these chunks (the question has weight 2 in the RRF), so the reranker call after the plan is short.
        Best effort: any failure only means no head start."""
        if not settings.RERANK_ENABLED:
            return
        try:
            vectors = await self.embedder.embed_queries([question])
            hits = (await self.retriever.search_vectors(vectors, notebook_id, document_id, settings.RETRIEVAL_POOL_SIZE))[0]
            await self._score_cached(question, await self._hydrate([h["chunk_id"] for h in hits if h.get("chunk_id")], {}))
        except Exception as exc:
            logger.warning(f"Prescore skipped: {type(exc).__name__}: {str(exc)[:120]}")

    async def _hydrate(self, chunk_ids: List[str], scores: Dict[str, float], notebook_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch full text from MongoDB, keeping the given order. Ids that do not come from a filtered search (cited in an earlier
        answer) pass `notebook_id`: chunks of any other notebook are dropped."""
        chunk_docs = [c for c in await self.chunk_repo.get_chunks_by_ids(chunk_ids) if notebook_id is None or c.notebook_id == notebook_id]
        return [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "page": c.page,
                "section": c.section,
                "chunk_type": c.chunk_type,
                "score": scores.get(c.chunk_id, 0.0),
                "content": c.content,
                "concept_ids": c.concept_ids,
                "flags": list(getattr(c, "flags", None) or []),
            }
            for c in chunk_docs
        ]

    async def retrieve_hydrated_chunks(
        self,
        query: str,
        notebook_id: str,
        document_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Plain single-query dense retrieval (inspector endpoint)."""
        hits = await self.retriever.search_hybrid(query, notebook_id, document_id, top_k)
        ids = [h["chunk_id"] for h in hits if h.get("chunk_id")]
        return await self._hydrate(ids, {h["chunk_id"]: h["score"] for h in hits})

    async def retrieve_multi_doc(
        self,
        plan: List[PlanItem],
        notebook_id: str,
        scope_document_ids: List[str],
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Several filings, `hybrid|item-rr15|rel50t8k` (settings, MULTIDOC_*): one hybrid search per plan item inside its own
        filings (all of `scope_document_ids` when the item names none), Qwen3 order of its head, then the chunks close to each
        search's best take equal slots (round robin) up to 10 chunks / 8,192 tokens; `limit` caps the chunks instead (no token cap)."""
        plan = expand_plan(plan, scope_document_ids, settings.MULTIDOC_MAX_SEARCHES)
        lanes, scores, tokens = await self._lanes(plan, notebook_id, scope_document_ids)
        return await self._hydrate(allocate(lanes, tokens, limit), scores)

    async def retrieve_by_content(
        self, question: str, notebook_id: str, document_ids: List[str], year_document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """R4, the routing that needs neither catalog nor language model (planner_fallback/fallback_eval.py `r4_year_top2`): one
        search with the question per document (among the documents whose tables head the question's year, when any), a document
        stays when its best Qwen score is >= half the best document's, and the two best always stay; then the usual allocation."""
        among = year_document_ids or document_ids
        lanes, scores, tokens = await self._lanes([PlanItem(question, [d]) for d in among], notebook_id, document_ids)
        best = [max(sc.values()) if sc else 0.0 for _, sc in lanes]
        top2 = set(sorted(range(len(lanes)), key=lambda i: -best[i])[:2])
        kept = [lane for i, lane in enumerate(lanes) if best[i] >= 0.5 * max(best, default=0.0) or i in top2]
        return await self._hydrate(allocate(kept, tokens), scores)

    async def _lanes(
        self, plan: List[PlanItem], notebook_id: str, scope_document_ids: List[str]
    ) -> Tuple[List[Tuple[List[str], Dict[str, float]]], Dict[str, float], Dict[str, int]]:
        """(ranking, Qwen scores of its head) per plan item, the best first-stage score per chunk, and token counts."""
        t0 = time.perf_counter()
        dense, sparse = await self.embedder.embed_queries_with_sparse([item.query for item in plan])
        t1 = time.perf_counter()
        ranked = await self.retriever.search_vectors(
            dense,
            notebook_id,
            scope_document_ids,
            settings.MULTIDOC_CANDIDATE_LIMIT,
            per_vector_documents=[item.document_ids for item in plan],
        )
        t2 = time.perf_counter()
        stats = await self.chunk_repo.get_sparse_weights(list({h["chunk_id"] for hits in ranked for h in hits if h.get("chunk_id")}))
        t3 = time.perf_counter()
        scores: Dict[str, float] = {}
        for hits in ranked:
            for h in hits:
                scores[h["chunk_id"]] = max(h["score"], scores.get(h["chunk_id"], float("-inf")))
        lanes = [(hybrid_order(hits, q, stats)[: settings.MULTIDOC_PER_ITEM_LIMIT], {}) for hits, q in zip(ranked, sparse)]
        top_n = settings.MULTIDOC_RERANK_TOP_N
        if settings.RERANK_ENABLED and top_n > 1:
            try:
                lanes = await self._rerank_items(plan, [r for r, _ in lanes], scores, top_n)
            except RuntimeError as exc:  # e.g. GPU out of memory: the first-stage order still answers
                logger.warning(f"Multi-document reranking skipped: {type(exc).__name__}: {str(exc)[:120]}")
        logger.info(f"Multi-document search, {len(plan)} searches: embed {t1 - t0:.2f}s, vector {t2 - t1:.2f}s, sparse {t3 - t2:.2f}s, "
                    f"rerank {time.perf_counter() - t3:.2f}s")
        return lanes, scores, {cid: tok for cid, (_, tok) in stats.items()}

    async def _rerank_items(
        self, plan: List[PlanItem], rankings: List[List[str]], scores: Dict[str, float], top_n: int
    ) -> List[Tuple[List[str], Dict[str, float]]]:
        """(ranking, Qwen scores of its head) per plan item: Qwen3 orders each item's first `top_n` against that item's query
        (plain Qwen order, not fusion: item-rr15 83.9 vs item-fus15 83.1 on multi-doc dev)."""
        wanted = list(dict.fromkeys(cid for ranking in rankings for cid in ranking[:top_n]))
        text = {c["chunk_id"]: c["content"] for c in await self._hydrate(wanted, scores)}
        heads = [[cid for cid in ranking[:top_n] if cid in text] for ranking in rankings]
        pairs = list(dict.fromkeys((item.query, cid) for item, head in zip(plan, heads) for cid in head))  # one batched call for all searches
        score = dict(zip(pairs, await self.reranker.score_pairs([(q, text[cid]) for q, cid in pairs])))
        out: List[Tuple[List[str], Dict[str, float]]] = []
        for item, ranking, head in zip(plan, rankings, heads):
            qwen = {cid: score[(item.query, cid)] for cid in head}
            out.append((sorted(head, key=lambda cid: -qwen[cid]) + [cid for cid in ranking if cid not in qwen], qwen))
        return out

    async def safety_net(
        self, question: str, plan_queries: List[str], notebook_id: str, document_ids: List[str], exclude: Sequence[str]
    ) -> List[Tuple[Dict[str, Any], int]]:
        """Stream 2: the documents the plan does not search, each with the single-document lane (dense RRF [question x2, plan queries
        x1], first NET_FIRST_STAGE each, pool NET_POOL), Qwen3 by the question, best first. Returns (chunk, tokens) for the chunks
        scoring >= NET_GATE; the caller gives them the extra slots. Any reranker failure returns [] (the plan's chunks still answer)."""
        if not document_ids:
            return []
        queries = [question] + [q for q in dict.fromkeys(plan_queries) if q != question][:3]
        vectors = await self.embedder.embed_queries(queries)
        pool: List[str] = []
        for doc_id in document_ids:
            ranked = await self.retriever.search_vectors(vectors, notebook_id, doc_id, settings.NET_FIRST_STAGE)
            pool += rrf_merge([[h["chunk_id"] for h in hits] for hits in ranked], [2.0] + [1.0] * (len(queries) - 1))[: settings.NET_POOL]
        skip = set(exclude)
        chunks = await self._hydrate(list(dict.fromkeys(c for c in pool if c not in skip)), {})
        if not chunks:
            return []
        try:
            qwen = await self._score_cached(question, chunks)
        except RuntimeError as exc:
            logger.warning(f"Safety net skipped: {type(exc).__name__}: {str(exc)[:120]}")
            return []
        tokens = {cid: tok for cid, (_, tok) in (await self.chunk_repo.get_sparse_weights([c["chunk_id"] for c in chunks])).items()}
        passed = sorted(((s, c) for s, c in zip(qwen, chunks) if s >= settings.NET_GATE), key=lambda x: -x[0])
        for s, c in passed:
            c["score"], c["via"] = float(s), "safety_net"
        return [(c, tokens.get(c["chunk_id"], 0)) for _, c in passed]

    async def retrieve_research(
        self,
        question: str,
        sub_queries: List[str],
        notebook_id: str,
        document_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Research configuration: dense RRF over [question x2, sub-queries x1] -> pool 20 -> Qwen3 rerank fusion -> top 6."""
        queries = [question] + sub_queries[: settings.SUBQUERY_COUNT]
        vectors = await self.embedder.embed_queries(queries)
        ranked = await self.retriever.search_vectors(vectors, notebook_id, document_id, settings.FIRST_STAGE_LIMIT)

        scores: Dict[str, float] = {}
        for hits in ranked:
            for h in hits:
                scores[h["chunk_id"]] = max(h["score"], scores.get(h["chunk_id"], float("-inf")))
        fused = rrf_merge([[h["chunk_id"] for h in hits] for hits in ranked], [2.0] + [1.0] * (len(queries) - 1))
        pool = await self._hydrate(fused[: settings.RETRIEVAL_POOL_SIZE], scores)

        if settings.RERANK_ENABLED and len(pool) > 1:
            try:
                rerank_scores = await self._score_cached(question, pool)
                pool = fuse_with_rerank(pool, rerank_scores)
            except RuntimeError as exc:  # e.g. GPU out of memory even after the models took turns
                # An answer from the first-stage order (86.7 R@6 in the research) beats no answer.
                logger.warning(f"Reranking skipped, using first-stage order: {type(exc).__name__}: {exc} | {memory_report()}")
        return pool[: settings.RETRIEVAL_TOP_K]
