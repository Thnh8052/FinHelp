"""Intent of a message the rules (input_policy.decide) let through: is it a question about the selected reports, or small talk, an
off-topic request, a request for investment advice... Decided by the message's nearest example messages (intent_examples.json), compared
as BGE-M3 vectors: one short encode on the embedding model that retrieval already keeps loaded, and no language-model call.

Conservative, as the rules are: a message is turned away only when it is clearly closer to an out-of-scope intent than to any question
about a report (MIN_SCORE, MARGIN, measured in experiments/guardrail_eval). Everything else goes on to the search as before.
"""
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

import numpy as np

from app.modules.query_router.input_policy import unaccented

REPORT = "report_question"
# intent -> (action of the reply, key of its text in input_policy.MSG)
ROUTES = {
    "small_talk": ("static_reply", "small_talk"),
    "assistant_meta": ("static_reply", "capabilities"),
    "finance_concept": ("refuse_concept", "refuse_concept"),
    "investment_advice": ("refuse_advice", "refuse_advice"),
    "off_topic": ("refuse_out_of_domain", "refuse_out_of_domain"),
    "prompt_attack": ("refuse_instruction", "refuse_instruction"),
    "sensitive": ("refuse_sensitive", "refuse_sensitive"),
}
# What keeps a message in the search whatever it resembles: the kinds of evidence (Decision.evidence) that tie it to the selected reports.
# A definition of a filing's own vocabulary stays a definition ("what is an annual report") and a harmful request stays one when it
# says "report" ("how to falsify a financial report"), so a report term keeps neither; a request for advice stays one when it names a
# selected company ("is AMD a buy"), so the company does not keep it. Definitions of a line item ("ROE là gì") and the usual ways of
# asking for advice are refused by the rules before the router is asked.
KEPT_BY = {
    "small_talk": {"company", "document", "metric", "term"},
    "assistant_meta": {"company", "document", "metric", "term"},
    "off_topic": {"company", "document", "metric", "term"},
    "prompt_attack": {"company", "document", "metric", "term"},
    "sensitive": {"company", "document", "metric"},
    "finance_concept": {"company", "document", "metric", "year"},
    "investment_advice": {"document", "metric", "term"},
}
# Measured in experiments/guardrail_eval: legitimate questions come as close as 0.10 above their nearest report example (short ones,
# and Vietnamese typed without accents), messages that are really out of scope mostly more
MIN_SCORE = 0.55  # cosine similarity to the nearest example of the intent
MARGIN = 0.10  # and that much above the nearest example of a report question
Embed = Callable[[List[str]], Awaitable[List[List[float]]]]


@dataclass
class Intent:
    label: str  # the nearest out-of-scope intent
    score: float  # similarity to its nearest example
    report: float  # similarity to the nearest example of a report question
    blocked: bool  # the message is turned away with the reply of `label`

    def trace(self) -> Dict[str, object]:
        return {"label": self.label if self.blocked else REPORT, "nearest": self.label, "score": round(self.score, 3), "report": round(self.report, 3)}


def examples() -> Dict[str, List[str]]:
    """The example messages of each intent, each also without accents (people often type Vietnamese that way)."""
    data = json.loads(Path(__file__).with_name("intent_examples.json").read_text(encoding="utf-8"))
    return {label: list(dict.fromkeys(t for text in texts for t in (text, unaccented(text)))) for label, texts in data.items()}


def _unit(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    m = np.asarray(vectors, dtype=np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-9)


_index: Optional[tuple] = None  # (unit vectors of the examples, their intents): encoded once per process, on the first question
_lock = asyncio.Lock()


async def _examples_index(embed: Embed) -> tuple:
    global _index
    async with _lock:
        if _index is None:
            pairs = [(label, text) for label, texts in examples().items() for text in texts]
            _index = (_unit(await embed([text for _, text in pairs])), np.array([label for label, _ in pairs]))
    return _index


async def classify(question: str, embed: Embed, evidence: Sequence[str] = ()) -> Intent:
    """The nearest out-of-scope intent of `question` and whether it is turned away. `embed` is the query encoder
    (DenseEmbeddingService.embed_queries); `evidence` is how the rules found the question tied to the selected reports."""
    vectors, labels = await _examples_index(embed)
    sims = vectors @ _unit((await embed([question.strip()]))[0])
    report = float(sims[labels == REPORT].max())
    label, score = max(((lb, float(sims[labels == lb].max())) for lb in ROUTES), key=lambda x: x[1])
    blocked = score >= MIN_SCORE and score - report >= MARGIN and not (KEPT_BY[label] & set(evidence))
    return Intent(label, score, report, blocked)
