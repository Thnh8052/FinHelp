"""How a document is shown to the query router and the input policy: its label, catalog line, source card and scope entry."""
from typing import Any, Dict, List, Optional

from app.models.document import DocumentRecord
from app.services.query_router.input_policy import SourceInfo
from app.services.query_router.planner import CatalogEntry, clean_label
from app.services.query_router.target_resolver import Filing
from app.services.query_router.target_scope import ScopeDoc


def document_label(doc: DocumentRecord) -> str:
    """"Company | form | FY2022 (2022-01-30 to 2023-01-28)" from the header read at upload; the file name when the header could not be
    read. The dates let the answer state the months a figure covers when companies name the same fiscal year differently."""
    m = doc.metadata
    period = f"FY{m.fiscal_year}" + (f" Q{m.fiscal_quarter}" if m.fiscal_quarter else "") if m.fiscal_year else ""
    if period and m.period_end:
        period += f" ({m.period_start} to {m.period_end})" if m.period_start else f" (ended {m.period_end})"
    parts = [clean_label(p) for p in (m.company_name, m.report_type, period) if p]
    label = " | ".join(p for p in parts if p) or clean_label(doc.file_name)
    return label + (" [identity typed by the user, not found in the document]" if m.user_override_unverified else "")


def catalog_entry(doc: DocumentRecord) -> CatalogEntry:
    m = doc.metadata
    period = f"FY{m.fiscal_year}" + (f" Q{m.fiscal_quarter}" if m.fiscal_quarter else "") if m.fiscal_year else ""
    return CatalogEntry(doc.document_id, m.company_name or "", m.report_type or "", period, doc.file_name)


def source_info(doc: DocumentRecord) -> SourceInfo:
    m = doc.metadata
    return SourceInfo(m.company_name or "", m.report_type or "", m.fiscal_year, m.fiscal_quarter, document_label(doc), doc.page_count, doc.file_name,
                      list(m.years_covered))


def catalog_card(doc: DocumentRecord) -> Dict[str, Any]:
    """The catalog line in the shape catalog_route.py reads (entity, aliases, period = year the period ends, fiscal year / quarter)."""
    m = doc.metadata
    period = f"FY{m.period_end[:4]}" if m.period_end else (f"FY{m.fiscal_year}" if m.fiscal_year else "")
    return {"entity": m.company_name or "", "aliases": list(m.aliases), "ticker": m.ticker, "period": period, "fiscal_year": m.fiscal_year,
            "fiscal_quarter": m.fiscal_quarter, "years_covered": list(m.years_covered)}


def scope_doc(doc: DocumentRecord) -> ScopeDoc:
    m = doc.metadata
    return ScopeDoc(doc.document_id, document_label(doc), catalog_card(doc),
                    Filing(doc.document_id, m.company_name or doc.file_name, m.report_type or "", m.fiscal_year, m.fiscal_quarter,
                           m.comparable_year, m.period_end), list(m.years_covered))


def text_years(scope: List[DocumentRecord]) -> Dict[str, Optional[int]]:
    """Latest year heading each document's tables (code, no model): the year R5-on-text and R4 match the question against."""
    return {d.document_id: max(d.metadata.years_covered, default=None) for d in scope}
