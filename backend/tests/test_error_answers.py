"""The answers a refusal sends: a code and its params, and a refused form's codes field by field (see app/core/error_codes.py)."""
import json

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.error_codes import Code, api_error
from app.core.exceptions import DomainException
from app.main import domain_exception_handler, validation_exception_handler
from app.modules.documents.catalog_edit import CatalogUpdate


def test_a_refusal_carries_its_code_and_params():
    error = api_error(413, Code.FILE_TOO_LARGE, limit_mb=5)
    assert error.status_code == 413
    assert error.detail == {"code": "file_too_large", "params": {"limit_mb": 5}}


async def test_a_domain_failure_answers_its_code_and_params():
    answer = await domain_exception_handler(None, DomainException(Code.LLM_REJECTED, status=503))
    assert answer.status_code == 400
    assert json.loads(answer.body) == {"detail": {"code": "llm_rejected", "params": {"status": 503}}}


async def test_a_refused_form_names_each_field_with_its_code():
    with pytest.raises(ValidationError) as refused:
        CatalogUpdate(company_name="x" * 200, report_type="8-Q", fiscal_year=1800, ticker="bad ticker")
    answer = await validation_exception_handler(None, RequestValidationError(refused.value.errors()))

    body = json.loads(answer.body)
    assert answer.status_code == 422 and body["detail"]["code"] == Code.VALIDATION_FAILED
    by_code = {field["code"]: field for field in body["detail"]["fields"]}
    assert by_code[Code.CATALOG_NAME_INVALID]["params"] == {"max_chars": 120, "max_words": 8}
    assert by_code[Code.CATALOG_REPORT_TYPE_INVALID]["params"] == {}
    assert by_code[Code.CATALOG_YEAR_OUT_OF_RANGE]["params"]["min_year"] == 1990
    assert by_code[Code.CATALOG_TICKER_INVALID]["params"] == {}


async def test_a_field_without_a_catalog_code_reads_as_not_valid():
    with pytest.raises(ValidationError) as refused:
        CatalogUpdate(company_name="AMD", report_type="10-K")  # fiscal_year is missing
    answer = await validation_exception_handler(None, RequestValidationError(refused.value.errors()))
    fields = json.loads(answer.body)["detail"]["fields"]
    assert any(field["code"] == Code.INVALID_FIELD and field["params"] == {} for field in fields)
