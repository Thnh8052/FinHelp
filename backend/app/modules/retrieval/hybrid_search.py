import re
import sys
import time
from collections import Counter
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from qdrant_client import AsyncQdrantClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import logger
from app.modules.ingestion.chunk_repo import ChunkRepository
from app.modules.retrieval.embeddings import DenseEmbeddingService
from app.modules.query_router.planner import PlanItem, expand_plan
from app.modules.retrieval.fusion import fuse_with_rerank, round_robin_merge, rrf_merge
from app.modules.retrieval.gpu import memory_report
from app.modules.retrieval.qdrant_retriever import QdrantRetriever
from app.modules.retrieval.reranker import QwenRerankerService
from app.modules.retrieval.term_cache import TERMS


# Seconds spent in each part of the search of the question being served (set by the retrieval step, None elsewhere): they go into its trace.
SEARCH_PARTS: ContextVar = ContextVar("search_parts", default=None)


def part_done(name: str, since: float) -> float:
    """Add the time since `since` to part `name` of this question's search; returns the new clock reading."""
    now = time.perf_counter()
    parts = SEARCH_PARTS.get()
    if parts is not None:
        parts[name] = round(parts.get(name, 0.0) + now - since, 2)
    return now


def _z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / (x.std() + 1e-9)


_TERM = re.compile(r"[a-z0-9]+")


def bm25_scores(query: str, counts: Sequence[Counter]) -> np.ndarray:
    """BM25 (k1 1.5, b 0.75) of a query over the chunks of one search; df and the average length come from those chunks, as in the study (pool_coverage.py)."""
    terms = list(dict.fromkeys(_TERM.findall(query.lower())))
    if not terms or not counts:
        return np.zeros(len(counts))
    tf = np.array([[c.get(t, 0) for t in terms] for c in counts], dtype=np.float64)
    lengths = np.array([sum(c.values()) for c in counts], dtype=np.float64)
    df = (tf > 0).sum(0)
    idf = np.log(1 + (len(counts) - df + 0.5) / (df + 0.5))
    return (idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * lengths[:, None] / (lengths.mean() or 1.0)))).sum(1)


def dense_bm25_order(hits: Sequence[Dict[str, Any]], query: str, counts: Dict[str, Counter]) -> List[str]:
    """Chunk ids by 0.7 z(dense) + 0.3 z(BM25) over the search's hits (every chunk of its document)."""
    hits = [h for h in hits if h.get("chunk_id")]
    if not hits:
        return []
    ids = [h["chunk_id"] for h in hits]
    dense = np.array([h["score"] for h in hits], dtype=np.float64)
    w = settings.MULTIDOC_DENSE_WEIGHT
    score = w * _z(dense) + (1 - w) * _z(bm25_scores(query, [counts.get(cid, Counter()) for cid in ids]))
    return [ids[i] for i in np.argsort(-score, kind="stable")]


def planned_ceilings(documents: int) -> Tuple[int, int]:
    """(chunks, tokens) of a question with a plan: the chunks grow with the documents searched, the tokens are one cap. Replaced a token formula that grew with the number of
    searches without an upper limit (experiments/scripts/rag_improvement/d6_ceiling.py, 192 questions: the same compl, 85.4, as the formula; a cap of 8,192 loses 5 questions)."""
    return max(settings.MULTIDOC_MIN_CHUNKS, settings.MULTIDOC_CHUNKS_PER_FILE * documents), settings.MULTIDOC_PLANNED_MAX_TOKENS


def _near_best(ranking: List[str], scores: Dict[str, float]) -> List[str]:
    """The chunks scoring >= MULTIDOC_REL_THRESHOLD x the search's best Qwen score (at least its first chunk); a search without Qwen scores offers its whole ranking."""
    if not scores:
        return list(ranking)
    return [c for c in ranking if c in scores and scores[c] >= settings.MULTIDOC_REL_THRESHOLD * max(scores.values())] or ranking[:1]


def allocate_planned(lanes: Sequence[Tuple[List[str], Dict[str, float]]], tokens: Dict[str, int], max_chunks: int, max_tokens: int) -> List[str]:
    """The chunks of a question with a plan: each search keeps the chunks near its best, the last one (the search with the question) at most
    MULTIDOC_QUESTION_KEEP of them, then round robin up to the two ceilings (the first chunk always fits)."""
    kept = [_near_best(r, sc) for r, sc in lanes]
    kept[-1] = kept[-1][: settings.MULTIDOC_QUESTION_KEEP]
    out: List[str] = []
    used = 0
    for cid in round_robin_merge(kept, max_chunks):
        if out and used + tokens.get(cid, 0) > max_tokens:
            break
        out.append(cid)
        used += tokens.get(cid, 0)
    return out


def allocate(lanes: Sequence[Tuple[List[str], Dict[str, float]]], tokens: Dict[str, int], limit: Optional[int] = None) -> List[str]:
    """rel50t8k: from each search, the chunks scoring >= MULTIDOC_REL_THRESHOLD x its best Qwen score (at least its first chunk;
    a search without Qwen scores offers its whole ranking), merged round robin up to MULTIDOC_MAX_CHUNKS chunks and
    MULTIDOC_MAX_TOKENS tokens (the first chunk always fits). `limit`: that many chunks, no token cap."""
    kept = [_near_best(r, sc) for r, sc in lanes if r]
    out: List[str] = []
    used = 0
    for cid in round_robin_merge(kept, limit or settings.MULTIDOC_MAX_CHUNKS):
        if limit is None and out and used + tokens.get(cid, 0) > settings.MULTIDOC_MAX_TOKENS:
            break
        out.append(cid)
        used += tokens.get(cid, 0)
    return out


# ---------------------------------------------------------------- the evidence gate of the planned search (settings GATE_*, measured in experiments/scripts/mvp/gate_strong.py)
def gate_open(gaps: Dict[str, float], cut: float) -> List[str]:
    """The skipped documents to open: those whose dense gap (their best similarity to the question minus the best of the searched documents) is >= `cut`,
    the largest gap first. No cap of its own: a notebook holds at most MAX_SELECTED_DOCS_USER (5) documents and the plan searches at least one, so at most 4 are skipped
    (experiments/scripts/mvp/gate_five_docs.py: opening all of them is the best of 2 / 3 / 4)."""
    return sorted((d for d, g in gaps.items() if g >= cut), key=lambda d: -gaps[d])


def gate_pool(rankings: Sequence[Sequence[str]], size: int) -> List[str]:
    """The candidates of one opened document: rank fusion of its rankings, the first one (the question's) counted twice, the others (plan queries) once."""
    return rrf_merge([r[: settings.GATE_FIRST_STAGE] for r in rankings], [2.0] + [1.0] * (len(rankings) - 1))[:size] if rankings else []


def gate_extra(pools: Sequence[Sequence[str]], qwen: Dict[Tuple[str, str], float], question: str, plan_queries: Sequence[str], held: set, tokens: Dict[str, int], used: int) -> List[str]:
    """The chunks the gate adds: every candidate not already sent (`held`) is scored GATE_QUESTION_WEIGHT x P(yes | question) + the rest x its best P(yes | plan query)
    (the question's score alone without plan queries); the GATE_MAX_CHUNKS best scores >= GATE_MIN_SCORE over all opened documents enter, best first, while the context
    (`used` tokens already) stays within GATE_MAX_TOKENS: a chunk that does not fit is skipped and a later, shorter one may still enter. A candidate the reranker did not score
    for the question is never added."""
    w = settings.GATE_QUESTION_WEIGHT
    score: Dict[str, float] = {}
    for pool in pools:
        for cid in pool:
            if cid in held or (question, cid) not in qwen:
                continue
            others = [qwen[(q, cid)] for q in plan_queries if (q, cid) in qwen]
            score[cid] = qwen[(question, cid)] if not others else w * qwen[(question, cid)] + (1 - w) * max(others)
    out: List[str] = []
    for cid in sorted((c for c, s in score.items() if s >= settings.GATE_MIN_SCORE), key=lambda c: -score[c])[: settings.GATE_MAX_CHUNKS]:
        if used + tokens.get(cid, 0) > settings.GATE_MAX_TOKENS:
            continue
        out.append(cid)
        used += tokens.get(cid, 0)
    return out


def _note(name: str, value: float) -> None:
    """A fact of this question's search kept in its trace beside the seconds of each part (search_<name>)."""
    parts = SEARCH_PARTS.get()
    if parts is not None:
        parts[name] = value


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

    async def retrieve_planned(self, question: str, plan: List[PlanItem], notebook_id: str, scope_document_ids: List[str], *,
                               gate_document_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Q13af, the path of a question with a plan (settings, MULTIDOC_*): one search per (query, document) by dense + BM25, one more with the
        question by dense over the planned documents, Qwen3 orders each by its own query, then allocate_planned. Then the evidence gate (settings GATE_*):
        the documents of `gate_document_ids` (the whole selection when code narrowed the scope; default: the scope) that the plan does not search are looked at
        once, and the best chunks of those close to the question are appended after the main ones; their pairs are scored in the main reranker call."""
        t0 = time.perf_counter()
        searches = expand_plan(plan, scope_document_ids, sys.maxsize)
        if len(searches) > settings.MULTIDOC_SEARCH_GUARD:
            logger.warning(f"Plan with {len(searches)} searches: only the first {settings.MULTIDOC_SEARCH_GUARD} run")
            searches = searches[: settings.MULTIDOC_SEARCH_GUARD]
        documents = list(dict.fromkeys(d for s in searches for d in s.document_ids))
        items = searches + [PlanItem(question, documents)]
        vectors = await self.embedder.embed_queries([item.query for item in items])
        t = part_done("embed", t0)
        ranked = await self.retriever.search_vectors(
            vectors, notebook_id, scope_document_ids, settings.MULTIDOC_CANDIDATE_LIMIT, per_vector_documents=[item.document_ids for item in items]
        )
        t = part_done("vector", t)
        counts, tokens = await self._term_counts(documents)
        t = part_done("mongo_text", t)
        scores: Dict[str, float] = {}
        for hits in ranked:
            for h in hits:
                scores[h["chunk_id"]] = max(h["score"], scores.get(h["chunk_id"], float("-inf")))
        rankings = [dense_bm25_order(hits, s.query, counts)[: settings.MULTIDOC_PER_ITEM_LIMIT] for hits, s in zip(ranked, searches)]
        rankings.append([h["chunk_id"] for h in ranked[-1] if h.get("chunk_id")][: settings.MULTIDOC_QUESTION_POOL])
        t = part_done("bm25", t)
        pools, plan_queries, gate_pairs = await self._gate_candidates(question, plan, dict(zip((item.query for item in items), vectors)), ranked[-1], documents,
                                                                      gate_document_ids or scope_document_ids, notebook_id, counts, tokens, scores)
        t = part_done("gate", t)
        lanes, gate_scores = await self._qwen_lanes(items, rankings, scores, gate_pairs)
        t = part_done("rerank", t)
        max_chunks, max_tokens = planned_ceilings(len(documents))
        chosen = allocate_planned(lanes, tokens, max_chunks, max_tokens)
        added = gate_extra(pools, gate_scores, question, plan_queries, set(chosen), tokens, sum(tokens.get(c, 0) for c in chosen)) if pools else []
        if settings.GATE_ENABLED:
            _note("gate_added", len(added))
        opened = f", gate opened {len(pools)} documents and added {len(added)} chunks" if pools else ""
        logger.info(f"Planned search, {len(items)} searches, {len(documents)} documents: {len(chosen)} chunks (ceiling {max_chunks} / {max_tokens} tokens){opened} in {time.perf_counter() - t0:.2f}s")
        hydrated = await self._hydrate(chosen + added, scores)
        part_done("hydrate", t)
        return hydrated

    async def _gate_candidates(self, question: str, plan: List[PlanItem], vector_of: Dict[str, List[float]], planned_hits: Sequence[Dict[str, Any]], documents: Sequence[str],
                               selection: Sequence[str], notebook_id: str, counts: Dict[str, Counter], tokens: Dict[str, int], scores: Dict[str, float]
                               ) -> Tuple[List[List[str]], List[str], List[Tuple[str, str]]]:
        """(candidates of each opened document, the plan queries that also score them, the (query, chunk id) pairs for the reranker); three empty lists when the gate is off,
        no selected document was left out of the plan, or none is close enough to the question. The look costs one top-1 vector search per skipped document; an opened
        document costs one more search per query and the word counts of its chunks. `counts`, `tokens` and `scores` receive the opened documents' chunks."""
        searched = set(documents)
        skipped = [d for d in dict.fromkeys(selection) if d not in searched]
        if not settings.GATE_ENABLED or not skipped:
            return [], [], []
        best = max((h["score"] for h in planned_hits), default=0.0)  # the question's best similarity in the searched documents (its search is dense, over all of them)
        tops = await self.retriever.search_vectors([vector_of[question]] * len(skipped), notebook_id, list(selection), 1, per_vector_documents=[[d] for d in skipped])
        gaps = {d: hits[0]["score"] - best for d, hits in zip(skipped, tops) if hits}
        opened = gate_open(gaps, settings.GATE_OPEN_GAP)
        if gaps:
            _note("gate_gap", round(max(gaps.values()), 3))
        _note("gate_open", len(opened))
        if not opened:
            return [], [], []
        plan_queries = [q for q in dict.fromkeys(item.query for item in plan) if q != question][: settings.GATE_PLAN_QUERIES]
        asked = [question] + plan_queries
        hits = await self.retriever.search_vectors([vector_of[q] for _ in opened for q in asked], notebook_id, list(selection), settings.MULTIDOC_CANDIDATE_LIMIT,
                                                   per_vector_documents=[[d] for d in opened for _ in asked])
        more_counts, more_tokens = await self._term_counts(opened)
        counts.update(more_counts)
        tokens.update(more_tokens)
        pools: List[List[str]] = []
        for k in range(len(opened)):
            mine = hits[k * len(asked):(k + 1) * len(asked)]
            for found in mine:
                for h in found:
                    scores[h["chunk_id"]] = max(h["score"], scores.get(h["chunk_id"], float("-inf")))
            pools.append(gate_pool([dense_bm25_order(found, q, counts) for found, q in zip(mine, asked)], settings.GATE_POOL))
        pairs = [(q, cid) for pool in pools for cid in pool for q in asked]
        _note("gate_pairs", len(pairs))
        return pools, plan_queries, pairs

    async def _term_counts(self, documents: Sequence[str]) -> Tuple[Dict[str, Counter], Dict[str, int]]:
        """({chunk_id: word counts}, {chunk_id: token count}) of every chunk of the documents, counted once per document (term_cache.py)."""
        missing = [d for d in documents if TERMS.get(d) is None]
        if missing:
            for doc_id, chunks in (await self.chunk_repo.get_text_by_document(missing)).items():
                TERMS.put(doc_id, {cid: (Counter(_TERM.findall(text.lower())), tok) for cid, (text, tok) in chunks.items()})
        counts: Dict[str, Counter] = {}
        tokens: Dict[str, int] = {}
        for doc_id in documents:
            for cid, (words, tok) in (TERMS.get(doc_id) or {}).items():
                counts[cid], tokens[cid] = words, tok
        return counts, tokens

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
        """(ranking, Qwen scores of its head) per plan item, the best first-stage score per chunk, and token counts. First stage dense + BM25, as the path with a plan
        (15/11: it was dense + BGE-M3 lexical weights, 81.2 compl against 85.4 on 192 questions, no better than dense only: d6_scorer.py)."""
        t0 = time.perf_counter()
        vectors = await self.embedder.embed_queries([item.query for item in plan])
        t1 = time.perf_counter()
        ranked = await self.retriever.search_vectors(
            vectors,
            notebook_id,
            scope_document_ids,
            settings.MULTIDOC_CANDIDATE_LIMIT,
            per_vector_documents=[item.document_ids for item in plan],
        )
        t2 = time.perf_counter()
        counts, tokens = await self._term_counts(list(dict.fromkeys(d for item in plan for d in (item.document_ids or scope_document_ids))))
        t3 = time.perf_counter()
        scores: Dict[str, float] = {}
        for hits in ranked:
            for h in hits:
                scores[h["chunk_id"]] = max(h["score"], scores.get(h["chunk_id"], float("-inf")))
        lanes, _ = await self._qwen_lanes(plan, [dense_bm25_order(hits, item.query, counts)[: settings.MULTIDOC_PER_ITEM_LIMIT] for hits, item in zip(ranked, plan)], scores)
        logger.info(f"Multi-document search, {len(plan)} searches: embed {t1 - t0:.2f}s, vector {t2 - t1:.2f}s, bm25 {t3 - t2:.2f}s, "
                    f"rerank {time.perf_counter() - t3:.2f}s")
        return lanes, scores, tokens

    async def _qwen_lanes(self, plan: List[PlanItem], rankings: List[List[str]], scores: Dict[str, float], extra: Sequence[Tuple[str, str]] = ()
                          ) -> Tuple[List[Tuple[List[str], Dict[str, float]]], Dict[Tuple[str, str], float]]:
        """((ranking, Qwen scores of its head) per search, {(query, chunk id): Qwen score} of the `extra` pairs, scored in the same call); without the reranker
        (off, or it fails) the first-stage order still answers and no extra pair has a score."""
        top_n = settings.MULTIDOC_RERANK_TOP_N
        if settings.RERANK_ENABLED and top_n > 1:
            try:
                return await self._rerank_items(plan, rankings, scores, top_n, extra)
            except RuntimeError as exc:  # e.g. GPU out of memory
                logger.warning(f"Multi-document reranking skipped: {type(exc).__name__}: {str(exc)[:120]}")
        return [(r, {}) for r in rankings], {}

    async def _rerank_items(
        self, plan: List[PlanItem], rankings: List[List[str]], scores: Dict[str, float], top_n: int, extra: Sequence[Tuple[str, str]] = ()
    ) -> Tuple[List[Tuple[List[str], Dict[str, float]]], Dict[Tuple[str, str], float]]:
        """(ranking, Qwen scores of its head) per plan item: Qwen3 orders each item's first `top_n` against that item's query
        (plain Qwen order, not fusion: item-rr15 83.9 vs item-fus15 83.1 on multi-doc dev). The `extra` (query, chunk id) pairs (the evidence gate's) are
        scored in the same call and returned apart: one request to the reranker for the whole question."""
        wanted = list(dict.fromkeys([cid for ranking in rankings for cid in ranking[:top_n]] + [cid for _, cid in extra]))
        text = {c["chunk_id"]: c["content"] for c in await self._hydrate(wanted, scores)}
        heads = [[cid for cid in ranking[:top_n] if cid in text] for ranking in rankings]
        more = [(q, cid) for q, cid in extra if cid in text]
        pairs = list(dict.fromkeys([(item.query, cid) for item, head in zip(plan, heads) for cid in head] + more))  # one batched call for all searches
        score = dict(zip(pairs, await self.reranker.score_pairs([(q, text[cid]) for q, cid in pairs])))
        out: List[Tuple[List[str], Dict[str, float]]] = []
        for item, ranking, head in zip(plan, rankings, heads):
            qwen = {cid: score[(item.query, cid)] for cid in head}
            out.append((sorted(head, key=lambda cid: -qwen[cid]) + [cid for cid in ranking if cid not in qwen], qwen))
        return out, {pair: score[pair] for pair in more}

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
