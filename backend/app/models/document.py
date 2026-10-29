from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import BaseSchema, get_utc_now


class DocumentMetadata(BaseModel):
    """Business & structural metadata extracted from PDF."""

    company_name: Optional[str] = None
    ticker: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None  # 10-Q and earnings releases
    period_start: Optional[str] = None  # ISO date; 10-K when the prior year-end is printed
    period_end: Optional[str] = None  # ISO date the period ends (fiscal year names differ: Ulta 'fiscal 2022' and Best Buy 'fiscal 2023' both end 2023-01-28)
    comparable_year: Optional[int] = None  # 10-K: calendar year the fiscal year mostly covers (ends Jan-May -> previous year)
    report_type: Optional[str] = None  # catalog doc_type (annual financial statements, 10-K, 10-Q, ...) or the rule header's form
    aliases: List[str] = Field(default_factory=list)  # former names of the reporting company found in the text (Barrick Gold -> Barrick Mining)
    years_covered: List[int] = Field(default_factory=list)  # years heading the document's tables, current first (code, no model)
    catalog_source: Optional[str] = None  # "model" (catalog.py), "rule" (doc_header.py) or "user" (confirmed / edited in the UI)
    catalog_unverified: List[str] = Field(default_factory=list)  # catalog fields not found in the text: the UI asks the user
    catalog_confirmed: bool = False  # the owner confirmed / edited the catalog in the UI (PATCH /documents/{id}/catalog)
    user_override_unverified: List[str] = Field(default_factory=list)  # fields the user typed that the document text does not show
    name_candidates: List[Dict[str, Any]] = Field(default_factory=list)  # [{"name", "pages"}] legal names found in the text, best first
    catalog_history: List[Dict[str, Any]] = Field(default_factory=list)  # [{"at", "by", "old", "new"}] every user edit
    currency: Optional[str] = None  # unknown until extracted: a hard-coded "VND" is wrong for SEC filings
    unit_scale: Optional[str] = None
    audit_firm: Optional[str] = None


class DocumentRecord(BaseSchema):
    """Document record stored in MongoDB `documents` collection."""

    document_id: str = Field(..., description="Unique document ID (doc_001)")
    notebook_id: str = Field(..., description="Parent notebook ID")
    file_name: str
    file_size_bytes: int
    file_path: str = Field(..., description="Storage path in local filesystem or object storage")
    file_hash: Optional[str] = None
    page_count: int = 0
    parsing_status: str = Field(
        default="pending",
        description="'pending', 'processing', 'completed', 'failed'"
    )
    indexing_status: str = Field(
        default="pending",
        description="'pending', 'indexing', 'completed', 'failed'"
    )
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    error_message: Optional[str] = None
    parsing_engine: Optional[str] = Field(None, description="'docling', 'pymupdf' or 'pymupdf_fallback'")
    created_at: Any = Field(default_factory=get_utc_now)
    updated_at: Any = Field(default_factory=get_utc_now)

