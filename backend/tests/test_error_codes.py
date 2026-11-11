"""Error codes: every code the backend can send has a sentence in both interface languages, and no route writes a sentence itself.

A refused field is named by a code the form validators raise (catalog_edit.py); the interface looks the sentence up. A missing
sentence, or a raise that carries Vietnamese or English text, would reach the screen untranslated, so both are tests.
"""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.error_codes import FIELD_CODES, Code
from app.modules.documents.catalog_edit import CatalogUpdate

APP = Path(__file__).resolve().parents[1] / "app"
LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales"


def _all_codes() -> set:
    return {value for name, value in vars(Code).items() if name.isupper()}


def _errors_section(locale: str) -> set:
    """The keys of the `errors` section of a locale file (TypeScript, 4-space indented)."""
    text = (LOCALES / locale).read_text(encoding="utf-8")
    match = re.search(r"\n  errors: \{\n(.*?)\n  \},?\n", text, re.S)
    assert match, f"no `errors` section in {locale}"
    return set(re.findall(r"^    (\w+):", match.group(1), re.M))


@pytest.mark.parametrize("locale", ["en.ts", "vi.ts"])
def test_every_code_has_a_sentence_in_each_language(locale):
    missing = _all_codes() - _errors_section(locale)
    assert not missing, f"{locale} has no sentence for: {sorted(missing)}"


def test_no_raise_carries_a_sentence_of_its_own():
    offenders = []
    for path in APP.rglob("*.py"):
        if path.name == "error_codes.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"detail=f?[\"']", line):
                offenders.append(f"{path.relative_to(APP)}:{number}")
    assert not offenders, f"a raise carries a sentence, name a code instead: {offenders}"


def test_a_refused_catalog_field_names_its_code_and_params():
    with pytest.raises(ValidationError) as refused:
        CatalogUpdate(company_name="x" * 200, report_type="10-K", fiscal_year=2024)
    error = refused.value.errors()[0]
    assert error["type"] == Code.CATALOG_NAME_INVALID and error["type"] in FIELD_CODES
    assert error["ctx"] == {"max_chars": 120, "max_words": 8}
