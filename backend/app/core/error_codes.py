"""Error codes: the backend names WHAT went wrong, the interface writes the sentence in the user's language.

A refusal the interface can show is `{"detail": {"code": CODE, "params": {...}}}`; a refused form is
`{"detail": {"code": "validation_failed", "fields": [{"field", "code", "params"}]}}`.

The sentences live in frontend/src/locales/{en,vi}.ts under `errors`. tests/test_error_codes.py fails when a code has no sentence
in either language, or when a raise carries a sentence instead of a code. Add a code here, then its two sentences there.
"""
from typing import Optional

from fastapi import HTTPException


def api_error(status_code: int, code: str, headers: Optional[dict] = None, **params) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "params": params}, headers=headers)


class Code:
    # sign-in and accounts
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_NOT_AVAILABLE = "account_not_available"
    TOO_MANY_ATTEMPTS = "too_many_attempts"
    INVALID_RESET_CODE = "invalid_reset_code"
    WRONG_CURRENT_PASSWORD = "wrong_current_password"
    SESSION_EXPIRED = "session_expired"
    LOGIN_REQUIRED = "login_required"
    ADMIN_REQUIRED = "admin_required"
    USER_NOT_FOUND = "user_not_found"
    # notebooks and access
    NOTEBOOK_NOT_FOUND = "notebook_not_found"
    NOTEBOOK_FORBIDDEN = "notebook_forbidden"
    SAMPLE_NOTEBOOK_READ_ONLY = "sample_notebook_read_only"
    NOTEBOOK_BUSY_DELETE = "notebook_busy_delete"
    NOTEBOOK_DELETE_FAILED = "notebook_delete_failed"
    MESSAGE_NOT_FOUND = "message_not_found"
    GUEST_ALLOWANCE_USED = "guest_allowance_used"
    QUESTION_QUOTA_USED = "question_quota_used"
    # documents
    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    FILE_TOO_LARGE = "file_too_large"
    NOT_A_PDF = "not_a_pdf"
    DOCUMENT_SAME_NAME_PROCESSING = "document_same_name_processing"
    DOCUMENT_SAME_NAME = "document_same_name"
    GUEST_DOCUMENT_LIMIT = "guest_document_limit"
    NOTEBOOK_DOCUMENT_LIMIT = "notebook_document_limit"
    CONTENT_DUPLICATE_PROCESSING = "content_duplicate_processing"
    CONTENT_DUPLICATE = "content_duplicate"
    CONTENT_DUPLICATE_ANY = "content_duplicate_any"
    DOCUMENT_BUSY_DELETE = "document_busy_delete"
    DOCUMENT_DELETE_FAILED = "document_delete_failed"
    DOCUMENT_NOT_FOUND = "document_not_found"
    JOB_NOT_FOUND = "job_not_found"
    PDF_MISSING = "pdf_missing"
    # questions
    NO_SOURCE_SELECTED = "no_source_selected"
    TOO_MANY_SOURCES = "too_many_sources"
    MENTION_NOT_SELECTED = "mention_not_selected"
    QUESTION_TOO_LONG = "question_too_long"
    SOURCE_NOT_IN_NOTEBOOK = "source_not_in_notebook"
    SOURCE_NOT_READY = "source_not_ready"
    DOCUMENTS_BUSY = "documents_busy"
    SOURCE_FAILED = "source_failed"
    # document processing (also stored in a document's error_message)
    PARSE_FAILED = "parse_failed"
    NO_TEXT_EXTRACTED = "no_text_extracted"
    SYSTEM_NOT_READY = "system_not_ready"
    INGESTION_INTERRUPTED = "ingestion_interrupted"
    INGESTION_STALLED = "ingestion_stalled"
    INGESTION_UNEXPECTED = "ingestion_unexpected"
    # the language-model service
    LLM_NOT_CONFIGURED = "llm_not_configured"
    LLM_REJECTED = "llm_rejected"
    LLM_UNAVAILABLE = "llm_unavailable"
    # the search itself (the vector store or the network to it timed out or dropped, even after one more try)
    SEARCH_UNAVAILABLE = "search_unavailable"
    # generic
    INTERNAL_ERROR = "internal_error"
    VALIDATION_FAILED = "validation_failed"
    INVALID_FIELD = "invalid_field"
    # catalog form fields (raised by the validators in documents/catalog_edit.py)
    CATALOG_NAME_INVALID = "catalog_name_invalid"
    CATALOG_TICKER_INVALID = "catalog_ticker_invalid"
    CATALOG_ALIASES_TOO_MANY = "catalog_aliases_too_many"
    CATALOG_REPORT_TYPE_INVALID = "catalog_report_type_invalid"
    CATALOG_YEAR_OUT_OF_RANGE = "catalog_year_out_of_range"
    CATALOG_QUARTER_INVALID = "catalog_quarter_invalid"
    CATALOG_PERIOD_END_INVALID = "catalog_period_end_invalid"


# The field-level codes: a form validator raises one of these, and the 422 answer names it as is.
FIELD_CODES = frozenset(
    value for name, value in vars(Code).items() if name.startswith("CATALOG_")
)
