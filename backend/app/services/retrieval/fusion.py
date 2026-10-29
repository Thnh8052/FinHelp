"""Rank fusion used by the research configuration (all functions are pure and unit-tested)."""
from typing import Dict, Hashable, List, Sequence

RRF_K = 60


def rrf_merge(rankings: Sequence[Sequence[Hashable]], weights: Sequence[float], k: int = RRF_K) -> List[Hashable]:
    """Weighted reciprocal-rank fusion. Each ranking is best-first; an id missing from a ranking adds nothing.
    Ties keep first-seen order (stable), like the research code."""
    score: Dict[Hashable, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking):
            score[item] = score.get(item, 0.0) + weight / (k + rank)
    return sorted(score, key=lambda item: -score[item])


def round_robin_merge(rankings: Sequence[Sequence[Hashable]], limit: int) -> List[Hashable]:
    """Equal slots: take the best unseen item of every ranking in turn, until `limit` items are chosen.
    Used by the multi-document path, where each ranking belongs to one (filing, item) so every filing keeps its share."""
    merged: List[Hashable] = []
    seen = set()
    depth = 0
    longest = max((len(r) for r in rankings), default=0)
    while len(merged) < limit and depth < longest:
        for ranking in rankings:
            if depth < len(ranking) and ranking[depth] not in seen and len(merged) < limit:
                merged.append(ranking[depth])
                seen.add(ranking[depth])
        depth += 1
    return merged


def descending_ranks(scores: Sequence[float]) -> List[int]:
    """0-based rank of every score when sorted high to low (stable for ties)."""
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    ranks = [0] * len(scores)
    for rank, index in enumerate(order):
        ranks[index] = rank
    return ranks


def fuse_with_rerank(pool: Sequence[Hashable], rerank_scores: Sequence[float], k: int = RRF_K) -> List[Hashable]:
    """Final order = RRF of (first-stage position, reranker rank), equal weights: the 'Qwen fusion' of the research."""
    ranks = descending_ranks(rerank_scores)
    fused = [1.0 / (k + position) + 1.0 / (k + ranks[position]) for position in range(len(pool))]
    order = sorted(range(len(pool)), key=lambda i: -fused[i])
    return [pool[i] for i in order]
