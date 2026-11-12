"""The catalog form: what the owner may write into a document's identity (company, ticker, other names, report type, fiscal period).

Safety by structure, not by a word blacklist (a blacklist refuses real names such as "System1 Inc"):
- every field has a fixed shape (charset, length, word count, one line, enum, number range, ISO date), checked here on the server;
- a value the document text does not show is kept but listed in `user_override_unverified`, and the answer says the identity was typed
  by the user;
- the catalog never decides access (api/v1/deps.require_notebook does), and the planner can only pick among the selected documents.
"""
import datetime
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

from app.core.error_codes import Code

from app.modules.documents.document import DocumentRecord
from app.modules.ingestion.catalog import DOC_TYPES, _norm
from app.modules.ingestion.doc_header import comparable_year

REPORT_TYPES = DOC_TYPES + ["8-K"]  # the local model's document types + the rule header's forms
NAME = re.compile(r"[^\W_][\w&.,'\- ]*")  # starts with a letter or digit; letters, digits, spaces and & . , ' - only (no newline)
TICKER = re.compile(r"[A-Z0-9.\-]{1,10}")


def _name(value: str, max_chars: int, max_words: int) -> str:
    value = re.sub(r" {2,}", " ", value.strip())
    if not value or len(value) > max_chars or len(value.split()) > max_words or not NAME.fullmatch(value):
        raise PydanticCustomError(Code.CATALOG_NAME_INVALID, "invalid name", {"max_chars": max_chars, "max_words": max_words})
    return value


class CatalogUpdate(BaseModel):
    company_name: str
    ticker: Optional[str] = None
    aliases: List[str] = []
    report_type: str
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    period_end: Optional[str] = None

    @field_validator("company_name")
    @classmethod
    def _company(cls, v: str) -> str:
        return _name(v, 120, 8)

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        v = v.strip().upper()
        if not TICKER.fullmatch(v):
            raise PydanticCustomError(Code.CATALOG_TICKER_INVALID, "invalid ticker")
        return v

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: List[str]) -> List[str]:
        if len(v) > 5:
            raise PydanticCustomError(Code.CATALOG_ALIASES_TOO_MANY, "too many aliases", {"max": 5})
        return list(dict.fromkeys(_name(a, 60, 6) for a in v if a.strip()))

    @field_validator("report_type")
    @classmethod
    def _report_type(cls, v: str) -> str:
        if v not in REPORT_TYPES:
            raise PydanticCustomError(Code.CATALOG_REPORT_TYPE_INVALID, "invalid report type")
        return v

    @field_validator("fiscal_year")
    @classmethod
    def _year(cls, v: int) -> int:
        if not 1990 <= v <= datetime.date.today().year + 1:
            raise PydanticCustomError(Code.CATALOG_YEAR_OUT_OF_RANGE, "year out of range", {"min_year": 1990, "max_year": datetime.date.today().year + 1})
        return v

    @field_validator("fiscal_quarter")
    @classmethod
    def _quarter(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, 2, 3, 4):
            raise PydanticCustomError(Code.CATALOG_QUARTER_INVALID, "invalid quarter")
        return v

    @field_validator("period_end")
    @classmethod
    def _period_end(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        try:
            return datetime.date.fromisoformat(v.strip()).isoformat()
        except ValueError:
            raise PydanticCustomError(Code.CATALOG_PERIOD_END_INVALID, "invalid period end")


def needs_confirmation(doc: DocumentRecord) -> bool:
    """The owner must confirm the catalog before the document is asked about: a name or period the text does not show, or no name /
    fiscal year at all (the document could not be told apart from the others)."""
    m = doc.metadata
    return not m.catalog_confirmed and (bool(m.catalog_unverified) or not m.company_name or not m.fiscal_year)


def _in_text(value: str, text: str) -> bool:
    words = _norm(value)
    return bool(words) and f" {words} " in text


def catalog_changes(doc: DocumentRecord, req: CatalogUpdate, document_text: str, user: str) -> Dict[str, Any]:
    """The `$set` for an accepted form: the new fields, user source and confirmation, the typed values the text does not show, and the
    edit appended to the history (last 20)."""
    text = f" {_norm(document_text)} "
    unverified = [f for f, v in (("company_name", req.company_name), ("ticker", req.ticker)) if v and not _in_text(v, text)]
    unverified += [f"aliases:{a}" for a in req.aliases if not _in_text(a, text)]
    new = {"company_name": req.company_name, "ticker": req.ticker, "aliases": req.aliases, "report_type": req.report_type,
           "fiscal_year": req.fiscal_year, "fiscal_quarter": req.fiscal_quarter, "period_end": req.period_end,
           "comparable_year": comparable_year(req.period_end) if req.report_type == "10-K" else None}
    old = {k: getattr(doc.metadata, k) for k in new}
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = {"at": now.isoformat(), "by": user, "old": old, "new": new}
    return {**{f"metadata.{k}": v for k, v in new.items()},
            "catalog_confirmed_by": user, "catalog_confirmed_at": now,
            "metadata.catalog_source": "user", "metadata.catalog_confirmed": True, "metadata.catalog_unverified": [],
            "metadata.user_override_unverified": unverified, "metadata.catalog_history": (doc.metadata.catalog_history + [entry])[-20:]}
