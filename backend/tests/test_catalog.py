"""Catalog line read at upload (services/ingestion/catalog.py): code-side fields and the fallback when the model is unavailable."""
import json

import httpx

from app.services.ingestion import catalog

PAGES = {
    1: "## ROGERS COMMUNICATIONS INC.\nConsolidated Financial Statements\nDecember 31, 2023\nFormerly Rogers Cable Inc.",
    2: "| (In millions of Canadian dollars) | 2023 | 2022 |\n|---|---:|---:|\n| Revenue | 19,308 | 15,396 |",
    3: "| | 2023 | 2022 |\n|---|---:|---:|\n| Total assets | 69,964 | 51,903 |\n\n| Maturities | 2026 | 2027 |\n|---|---:|---:|\n| Debt | 1 | 2 |",
}


def test_card_metadata_checks_names_and_computes_years_and_fiscal_year():
    card = {"entity": "Rogers Communications Inc.", "aliases": ["Rogers Cable Inc.", "Shaw Communications"], "doc_type": "annual financial statements",
            "period_end": "2023-12-31", "fiscal_period": "fiscal 2024"}
    meta = catalog.card_metadata(card, PAGES)
    assert meta["company_name"] == "Rogers Communications Inc." and meta["catalog_unverified"] == []
    assert meta["aliases"] == ["Rogers Cable Inc."]  # Shaw is not in the text
    assert meta["fiscal_year"] == 2023  # "fiscal 2024" cannot name a year ending in December 2023: the period year is used
    assert meta["years_covered"] == [2023, 2022]  # 2026-2027 are after the period end


def test_card_metadata_flags_unverified_entity_and_bad_dates():
    meta = catalog.card_metadata({"entity": "Shaw Communications", "doc_type": "brochure", "period_end": "December 2023"}, PAGES)
    assert meta["company_name"] == "Shaw Communications" and set(meta["catalog_unverified"]) == {"entity", "period_end"}
    assert meta["report_type"] is None and meta["fiscal_year"] is None


def test_fiscal_label_quarters_and_period_descriptions():
    assert catalog.fiscal_label("Second Quarter Fiscal 2024", "2023-07-31") == (2024, 2)
    assert catalog.fiscal_label("fiscal 2022", "2023-01-01") == (2022, None)  # ends in January: the year before is allowed
    assert catalog.fiscal_label("Quarterly period ended October 31, 2022", "2022-10-31") == (None, None)


async def test_read_catalog_returns_none_when_disabled_or_unreachable(monkeypatch):
    from app.core.config import settings

    pages = [{"page_number": n, "text": t} for n, t in PAGES.items()]
    monkeypatch.setattr(settings, "CATALOG_ENABLED", False)
    assert await catalog.read_catalog(pages) is None

    monkeypatch.setattr(settings, "CATALOG_ENABLED", True)
    monkeypatch.setattr(settings, "CATALOG_BACKEND", "ollama")
    monkeypatch.setattr(catalog, "release_models", lambda: None)

    class Down:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("refused")

    monkeypatch.setattr(catalog.httpx, "AsyncClient", Down)
    assert await catalog.read_catalog(pages) is None


def test_prompt_has_first_pages_outline_and_no_file_name():
    prompt = catalog.build_prompt(PAGES)
    assert "FIRST PAGES" in prompt and "OUTLINE" in prompt and "p3: [table:" in prompt
    assert '"doc_type": one of ["annual financial statements"' in prompt


def test_interim_quarter_from_year_to_date_columns():
    from app.services.ingestion.catalog import card_metadata, interim_quarter
    six = {1: "| | Three Months Ended June 30, 2023 | Six Months Ended June 30, 2023 |"}
    assert interim_quarter(six) == 2
    assert interim_quarter({1: "Thirteen weeks ended Oct 29, 2022 | Thirty-nine weeks ended Oct 29, 2022"}) == 3
    assert interim_quarter({1: "Three months ended March 31, 2024"}) == 1
    card = {"entity": "unknown", "doc_type": "10-Q", "period_end": "2023-06-30", "fiscal_period": "Quarterly period ended June 30, 2023"}
    meta = card_metadata(card, six)
    assert (meta["fiscal_year"], meta["fiscal_quarter"]) == (2023, 2)
    annual = dict(card, doc_type="annual financial statements")
    assert card_metadata(annual, six)["fiscal_quarter"] is None


def test_vlm_fallback_accepts_a_logo_name_and_is_used_only_when_needed(monkeypatch, tmp_path):
    import asyncio
    import json as _json
    from app.services.ingestion import catalog

    pages = [{"page_number": 1, "text": "Consolidated Statements of Operations\n| | 2024 | 2023 |\n|---|---|---|\n| Revenue | 1 | 2 |"}]
    card = {"entity": "Air Canada", "doc_type": "annual financial statements", "period_end": "2024-12-31", "fiscal_period": "2024"}
    calls = []

    async def fake_chat(messages, **kw):
        calls.append(messages)
        return _json.dumps(card)

    monkeypatch.setattr(catalog, "chat_completion", fake_chat)
    monkeypatch.setattr(catalog, "_page_images", lambda path: ["aW1n"])
    meta = asyncio.run(catalog.read_catalog_vlm(tmp_path / "x.pdf", pages))
    assert meta["company_name"] == "Air Canada" and meta["catalog_source"] == "vlm" and meta["catalog_unverified"] == []
    assert calls[0][0]["content"][1]["type"] == "image_url"
    text_meta = catalog.card_metadata(card, {1: pages[0]["text"]})  # the local card cannot confirm a name it does not see
    assert text_meta["catalog_unverified"] == ["entity"] and catalog.needs_vlm(text_meta)
    assert not catalog.needs_vlm(meta) and catalog.needs_vlm(None)


async def test_catalog_through_the_api_uses_the_measured_prompt_and_the_same_checks(monkeypatch):
    from app.core.config import settings
    from app.services.llm.llm_client import LLMUnavailableError

    pages = [{"page_number": n, "text": t} for n, t in PAGES.items()]
    monkeypatch.setattr(settings, "CATALOG_ENABLED", True)
    monkeypatch.setattr(settings, "CATALOG_BACKEND", "deepseek")
    seen = {}

    async def fake(messages, **kw):
        seen["prompt"], seen["json"] = messages[0]["content"], kw.get("json_mode")
        return json.dumps({"entity": "Not In The Text Corp", "aliases": [], "doc_type": "10-K", "period_end": "2023-12-31", "fiscal_period": "fiscal 2023"})

    monkeypatch.setattr(catalog, "chat_completion", fake)
    meta = await catalog.read_catalog(pages)
    by_page = {int(p["page_number"]): p["text"] for p in pages}
    assert seen["json"] and seen["prompt"] == catalog.build_prompt(by_page)
    assert meta["catalog_source"] == "api" and "entity" in meta["catalog_unverified"] and meta["fiscal_year"] == 2023

    async def down(messages, **kw):
        raise LLMUnavailableError("down")

    monkeypatch.setattr(catalog, "chat_completion", down)
    assert await catalog.read_catalog(pages) is None
