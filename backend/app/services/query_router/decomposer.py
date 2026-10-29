import json
from typing import Dict, List, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.llm_client import LLMUnavailableError, chat_completion
from app.services.query_router.input_policy import detect_language

# Prompt of the research (decomp150.py): keyword sub-queries, no company name or year (the search is already
# restricted to the selected filing), no answering.
SYSTEM = "You write search queries for retrieving passages from ONE company's financial report. Output strictly valid JSON."
PROMPT = """The user asks a question about a single financial report. Write 2 to 5 short search queries that together retrieve every passage needed to answer it.

Rules:
1. If the question names a financial metric or ratio, expand it with its standard definition and write one query per financial statement that holds its inputs. Each query lists the input line items as they are usually labelled in financial statements (US GAAP, IFRS or UK GAAP), including common label variants (e.g. "purchases of property and equipment / capital expenditures").
2. If the question is about narrative information (business description, risks, segments, legal matters, drivers), write queries with the terms such a section would use.
3. Do not include the company name or the year; the search is already restricted to this report.
4. Do not answer the question.

Question: {q}
Output JSON only: {{"queries": ["...", "..."]}}"""
# A Vietnamese question is searched in English (the filings are English): the same call also translates it. English questions
# keep PROMPT unchanged, so the measured path is untouched.
PROMPT_VI = PROMPT.replace("4. Do not answer the question.\n", "4. Do not answer the question.\n"
                           "5. The question is in Vietnamese. Translate it into English as an analyst would ask it about the report (keep company "
                           "names, figures and fiscal periods as written) and write every query in English.\n").replace(
    '{{"queries": ["...", "..."]}}', '{{"question_en": "...", "queries": ["...", "..."]}}')

_cache: Dict[str, Tuple[str, List[str]]] = {}
_CACHE_MAX = 512


async def decompose_query(question: str) -> Tuple[str, List[str]]:
    """(question to search with, first SUBQUERY_COUNT keyword sub-queries). The search question is the question itself, or its
    English translation for a Vietnamese question. Any failure returns (question, []) so retrieval degrades to the question alone
    (the research measured 63.3 -> 80.7 R@6 for the gain the sub-queries give)."""
    if question in _cache:
        return _cache[question]
    vi = detect_language(question) == "vi"
    try:
        raw = await chat_completion(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": (PROMPT_VI if vi else PROMPT).format(q=question)}],
            max_tokens=400,
            json_mode=True,
        )
        parsed = json.loads(raw)
        queries = [q for q in parsed.get("queries", []) if isinstance(q, str) and q.strip()]
        english = parsed.get("question_en") if vi else None
    except (LLMUnavailableError, ValueError, AttributeError) as exc:
        logger.warning(f"Query decomposition skipped: {type(exc).__name__}")
        return question, []
    found = (english.strip() if isinstance(english, str) and english.strip() else question, queries[: settings.SUBQUERY_COUNT])
    if found[1]:
        if len(_cache) >= _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[question] = found
    return found
