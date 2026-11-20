"""The committed evaluation data (evals/data): gold v2 (200 multi-document questions written and checked by the students), the catalog of its 50 reports, and two
stored runs to score without calling anything: the TK-49 search (which evidence pages were in the excerpts) and the research answers of 20/11/2026."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict

DATA = Path(__file__).resolve().parent / "data"


def read_jsonl(path: Path) -> list:
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


@lru_cache(maxsize=1)
def questions() -> Dict[str, dict]:
    """{id: {id, question, workspace, required_docs, behavior, answer_spec, split}}"""
    return {q["id"]: q for q in read_jsonl(DATA / "gold_v2.jsonl")}


@lru_cache(maxsize=1)
def catalog() -> Dict[str, dict]:
    """{DOCUMENT: catalog meta (company, report type, fiscal year, years covered, aliases)}"""
    return {r["doc"]: r["meta"] for r in read_jsonl(DATA / "catalog.jsonl")}


def load_search(path: Path) -> Dict[str, dict]:
    """{id: {"comp": evidence complete by the page rule}} from a snapshot or from a retrieval_*.json of the research harness (rows with a "page" result)."""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    return {r["id"]: {**r, "comp": bool(r["comp"] if "comp" in r else r["page"]["comp"])} for r in rows if "comp" in r or "page" in r}


def load_answers(path: Path) -> Dict[str, dict]:
    """{id: {"answer", "status"}} from a jsonl with one answer per line (the snapshot, or the output of e2e_research / c2_search_deeper's first answers)."""
    return {r["id"]: r for r in read_jsonl(Path(path))}


@lru_cache(maxsize=1)
def search_snapshot() -> Dict[str, dict]:
    return load_search(DATA / "snapshots" / "search_tk49.json")


@lru_cache(maxsize=1)
def answer_snapshot() -> Dict[str, dict]:
    return load_answers(DATA / "snapshots" / "answers_e2e_2026-11-20.jsonl")
