"""Catalog line of a document, read at upload from its parsed text: who reports, which document type and period, which years have
figures. It is what the multi-document planner, the R5 routing and the "the selected documents do not have it" rules read.

Research: experiments/chunking/studies/doc_card/make_card.py --fields=slim (entity and period right on 52/52 non-SEC filings, names
50/50 on the SEC set, about 3 s a file on a 4 GB GPU). The model (qwen3:4b-instruct through Ollama, text of pages 1-2 + an outline
of the whole document) fills entity, aliases, doc_type, period_end and the printed fiscal label; code computes the period year,
years_covered and the fiscal year / quarter, and checks the names against the text. Never read from the file name.
When that card is missing or its name / period is unverified, read_catalog_vlm asks the paid language model with images of
pages 1-2 instead of their text (the design kept from the earlier VLM header: a name only in a logo is read from the image).
Ollama server as measured: OLLAMA_FLASH_ATTENTION=1 OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve (CATALOG_NUM_GPU=99 keeps every layer on
the GPU; the model is unloaded after each call so BGE-M3 and Qwen3 get the card back).
"""
import asyncio
import base64
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.llm_client import LLMUnavailableError, chat_completion
from app.services.retrieval.gpu import GPU_LOCK, release_models

YEAR = re.compile(r"(?<!\d)(?:19[5-9]\d|20\d\d)(?!\d)")  # not \b: "FY2023" has no word boundary before the year
QUARTER = {"q1": 1, "q2": 2, "q3": 3, "q4": 4, "first quarter": 1, "second quarter": 2, "third quarter": 3, "fourth quarter": 4}
# An interim report's longest year-to-date column names its quarter (labels often say only "Quarterly period ended ...")
YTD = [(re.compile(r"(?:nine[ -]months?|thirty[ -]nine[ -]weeks?)(?: period)? ended"), 3),
       (re.compile(r"(?:six[ -]months?|twenty[ -]six[ -]weeks?|half[ -]year)(?: period)? ended"), 2),
       (re.compile(r"(?:three[ -]months?|thirteen[ -]weeks?)(?: period)? ended"), 1)]
INTERIM = ("interim financial statements", "10-Q")
DOC_TYPES = ["annual financial statements", "interim financial statements", "annual report and accounts", "micro/abridged accounts",
             "MD&A", "10-K", "10-Q", "earnings release", "other"]
_W = re.compile(r"[A-Za-z0-9]+")

# The measured prompt (make_card.py, slim fields, text of 2 pages + full outline), word for word.
PROMPT = """You read a financial report and write its identity card. You get the text of its first 2 pages and, when given, an outline of the whole
document (one line per page: headings and the first row of each table). Use ONLY this text; write "unknown" (or []) when it is not stated.
{first}{outline}
Return JSON only:
{{"entity": "legal name of the reporting entity: the company whose financial statements these are, not a subsidiary, an acquired company or the auditor",
 "aliases": ["former names of that same company, only if the text says it was renamed; otherwise []"],
 "doc_type": one of {doc_types},
 "period_end": "YYYY-MM-DD, the last day of the reporting period",
 "fiscal_period": "the fiscal period label the company prints for this report, e.g. \\"fiscal 2024\\" or \\"Second Quarter Fiscal 2024\\"; \\"unknown\\" if none"}}"""


def outline(pages: Dict[int, str], cap: int = 14000) -> str:
    """One line per page: up to 3 headings, the first row of up to 2 tables (usually the period columns), the first words of the body
    (the addressee of the auditor's report names the company when the cover shows it only in a logo)."""
    lines = []
    for n, md in pages.items():
        heads = [re.sub(r"^#+\s*", "", line).strip() for line in md.splitlines() if line.startswith("#")][:3]
        table_heads, in_table = [], False
        for line in md.splitlines():
            row = line.lstrip().startswith("|")
            if row and not in_table:
                table_heads.append(" ".join(c.strip() for c in line.strip().strip("|").split("|") if c.strip())[:90])
            in_table = row
        body = " ".join(" ".join(line for line in md.splitlines() if line.strip() and not line.startswith(("#", "|", "<!--"))).split()[:12])
        parts = heads + [f"[table: {t}]" for t in table_heads[:2]] + ([body] if body else [])
        lines.append(f"p{n}: " + " | ".join(parts)[:240])
    text = "\n".join(lines)
    return text if len(text) <= cap else text[:cap] + "\n(outline truncated)"


def build_prompt(pages: Dict[int, str], n_pages: int = 2, cap: int = 3000) -> str:
    first = "\n\n".join(f"[page {n}]\n{pages[n][:cap]}" for n in sorted(pages)[:n_pages])
    return PROMPT.format(first=f"\nFIRST PAGES\n{first}\n", outline=f"\nOUTLINE\n{outline(pages)}\n", doc_types=json.dumps(DOC_TYPES))


def fiscal_label(label: Any, period_end: str = "") -> tuple:
    """(fiscal year, quarter or None) from the label the model copied ("Second Quarter Fiscal 2024" -> (2024, 2)); (None, None) if no
    year, if it describes the period ("Quarterly period ended ..."), or if a full-year label cannot name a year ending on period_end:
    a year ending July-December is named by its end year, one ending January-June by its end year or the year before (Walmart
    FY2024 ends 2024-01-31). Quarter labels are not checked (Salesforce Q2 fiscal 2024 ends 2023-07-31)."""
    s = str(label or "").lower()
    y = YEAR.search(s)
    if re.search(r"\bend(?:ed|ing)\b", s):
        return None, None
    q = next((n for k, n in QUARTER.items() if re.search(rf"(?<![a-z0-9]){k}(?![a-z0-9])", s)), None)
    m = re.fullmatch(r"(\d{4})-(\d{2})-\d{2}", str(period_end or ""))
    if y and m and q is None and int(y[0]) not in ({int(m[1])} if int(m[2]) >= 7 else {int(m[1]), int(m[1]) - 1}):
        return None, None
    return (int(y[0]), q) if y else (None, None)


def years_covered(pages: Dict[int, str], period_end: str = "") -> List[int]:
    """Years in the header rows (first two rows) of the document's tables, current first. A year must head at least 30% as many tables
    as the most frequent one (drops a lone note table with old years) and not be after the period end (drops maturity schedules)."""
    end = int(period_end[:4]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(period_end)) else 9999
    count: Dict[int, int] = {}
    rows: List[str] = []
    for md in pages.values():
        for line in md.splitlines() + [""]:
            if line.lstrip().startswith("|"):
                if not all(set(c.strip()) <= set(":- ") for c in line.strip().strip("|").split("|")):
                    rows.append(line)
            elif rows:
                for yr in {int(v) for v in YEAR.findall(" ".join(rows[:2]))}:
                    if yr <= end:
                        count[yr] = count.get(yr, 0) + 1
                rows = []
    top = max(count.values(), default=0)
    return sorted((yr for yr, n in count.items() if n >= max(2 if top >= 5 else 1, 0.3 * top)), reverse=True)


def interim_quarter(pages: Dict[int, str]) -> Optional[int]:
    """Quarter of an interim report from its year-to-date columns: nine months (39 weeks) -> 3, six months (26 weeks) -> 2, three
    months (13 weeks) only -> 1. Right on the 6 SEC 10-Qs whose label gives no quarter (Apple, Corning, Netflix, PayPal, Salesforce,
    Foot Locker)."""
    text = " ".join(pages.values()).lower()
    return next((q for pattern, q in YTD if pattern.search(text)), None)


def _norm(s: str) -> str:
    return " ".join(_W.findall((s or "").lower()))


def card_metadata(card: Dict[str, Any], pages: Dict[int, str], source: str = "model") -> Dict[str, Any]:
    """DocumentMetadata fields from the model's JSON. Names not found in the text are kept but listed in catalog_unverified (the UI
    asks the user to confirm them); an alias not in the text is dropped. source "vlm": the name was read from the page image, so a
    name missing from the text (a logo) is not flagged."""
    full = _norm(" ".join(pages.values()))
    entity = str(card.get("entity") or "").strip()
    entity = "" if entity.lower() == "unknown" else entity
    pe = str(card.get("period_end") or "")
    pe = pe if re.fullmatch(r"\d{4}-\d{2}-\d{2}", pe) else ""
    fy, fq = fiscal_label(card.get("fiscal_period"), pe)
    doc_type = card.get("doc_type") if card.get("doc_type") in DOC_TYPES else None
    if fq is None and doc_type in INTERIM:
        fq = interim_quarter(pages)
    unverified = [k for k, ok in (("entity", entity and (source == "vlm" or _norm(entity) in full)), ("period_end", bool(pe))) if not ok]
    return {
        "company_name": entity or None,
        "aliases": [a for a in card.get("aliases") or [] if isinstance(a, str) and _norm(a) and _norm(a) in full and _norm(a) != _norm(entity)],
        "report_type": doc_type,
        "fiscal_year": fy or (int(pe[:4]) if pe else None),
        "fiscal_quarter": fq,
        "period_end": pe or None,
        "years_covered": years_covered(pages, pe),
        "catalog_source": source,
        "catalog_unverified": unverified,
    }


async def read_catalog(pages: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Catalog metadata of a parsed document ([{"page_number", "text"}]), or None when the model is off or unreachable or answers
    no JSON (the caller then falls back to the rule header). CATALOG_BACKEND "deepseek": the same prompt through the API (no GPU);
    "ollama": the local model, serialised with the other GPU jobs."""
    if not settings.CATALOG_ENABLED:
        return None
    by_page = {int(p["page_number"]): p.get("text") or "" for p in pages}
    if settings.CATALOG_BACKEND == "deepseek":
        try:
            card = json.loads(await chat_completion([{"role": "user", "content": build_prompt(by_page)}], max_tokens=600, json_mode=True))
        except (LLMUnavailableError, ValueError, TypeError) as exc:
            logger.warning(f"Catalog API unavailable: {type(exc).__name__}: {str(exc)[:160]}")
            return None
        return card_metadata(card, by_page, "api") if isinstance(card, dict) else None
    body = {"model": settings.CATALOG_MODEL, "stream": False, "format": "json", "keep_alive": 0,
            "options": {"num_ctx": settings.CATALOG_NUM_CTX, "temperature": 0, "num_gpu": settings.CATALOG_NUM_GPU},
            "messages": [{"role": "user", "content": build_prompt(by_page)}]}
    try:
        async with GPU_LOCK:
            release_models()
            async with httpx.AsyncClient(timeout=settings.CATALOG_TIMEOUT_SECONDS) as client:
                r = await client.post(f"{settings.CATALOG_OLLAMA_URL}/api/chat", json=body)
        r.raise_for_status()
        card = json.loads(r.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        logger.warning(f"Catalog model unavailable: {type(exc).__name__}: {str(exc)[:160]}")
        return None
    if not isinstance(card, dict):
        return None
    return card_metadata(card, by_page)


def needs_vlm(meta: Optional[Dict[str, Any]]) -> bool:
    """No local card, or its name / period could not be confirmed."""
    return meta is None or bool(meta.get("catalog_unverified")) or not meta.get("company_name") or not meta.get("fiscal_year")


def _page_images(pdf_path: Path, n: int = 2, dpi: int = 150) -> List[str]:
    import fitz  # PyMuPDF

    with fitz.open(str(pdf_path)) as doc:
        return [base64.b64encode(doc[i].get_pixmap(dpi=dpi).tobytes("png")).decode() for i in range(min(n, len(doc)))]


async def read_catalog_vlm(pdf_path: Path, pages: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Catalog metadata from images of pages 1-2 (+ the text outline) through the paid language model; None when it is off,
    unavailable or answers no JSON. Same prompt and checks as the local card."""
    if not settings.CATALOG_VLM_ENABLED:
        return None
    by_page = {int(p["page_number"]): p.get("text") or "" for p in pages}
    try:
        images = await asyncio.to_thread(_page_images, pdf_path)
        text = PROMPT.format(first="\nFIRST PAGES: the attached images of pages 1-2\n", outline=f"\nOUTLINE\n{outline(by_page)}\n",
                             doc_types=json.dumps(DOC_TYPES))
        content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + b}} for b in images]
        card = json.loads(await chat_completion([{"role": "user", "content": content}], max_tokens=1200, json_mode=True))
    except (LLMUnavailableError, ValueError, OSError, RuntimeError) as exc:
        logger.warning(f"Catalog image fallback unavailable: {type(exc).__name__}: {str(exc)[:160]}")
        return None
    return card_metadata(card, by_page, "vlm") if isinstance(card, dict) else None
