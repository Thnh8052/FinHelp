"""Page-bounded, structure-aware chunking ("st1024" of the research).

A page is split into units: heading + table (+ short intro paragraph before it, footnotes after it) and plain
paragraphs. Units are packed in order up to CHUNK_TOKENS BGE-M3 tokens; a chunk never crosses a page, so every
chunk has an exact page for citations. Tables are never cut in the middle of a row; an oversized table is split by
rows and repeats its header. The algorithm is the one measured in the research (docs/chunking_experiments).
"""
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.config import settings
from app.models.chunk import ChunkDocument

HEAD = re.compile(r"^#{1,6} ")
SEP = re.compile(r"^\|[\s:\-|]+\|\s*$")
FOOT = re.compile(r"^(\(\w{1,3}\)|\[\w{1,3}\]|[*†‡§]+|\d{1,2}\))\s")
UNIT = re.compile(r"\b(millions|thousands|billions)\b", re.I)
INTRO_MAX_TOKENS = 150
MIN_TAIL_TOKENS = 100

_tokenizer = None


def bge_m3_token_counter() -> Callable[[str], int]:
    """Token counter using the BGE-M3 tokenizer (tokenizer only, no model weights)."""
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(settings.DEFAULT_EMBEDDING_MODEL, use_fast=True)
    tokenizer = _tokenizer
    cache: Dict[str, int] = {}

    def count(text: str) -> int:
        if not text:
            return 0
        if text not in cache:
            cache[text] = len(tokenizer.encode(text, add_special_tokens=False))
        return cache[text]

    return count


def parse_blocks(md: str) -> List[Tuple[str, str]]:
    """Markdown -> [(kind, text)], kind: h heading, t table, p paragraph."""
    out: List[Tuple[str, str]] = []
    buf: List[str] = []
    kind: Optional[str] = None
    for line in md.split("\n"):
        k = "h" if HEAD.match(line) else "t" if line.startswith("|") else None
        if k is None:
            if line.strip() == "":
                if buf:
                    out.append((kind, "\n".join(buf)))
                    buf, kind = [], None
                continue
            k = "p"
        if k == "h":
            if buf:
                out.append((kind, "\n".join(buf)))
                buf, kind = [], None
            out.append(("h", line))
            continue
        if kind not in (None, k):
            out.append((kind, "\n".join(buf)))
            buf = []
        kind = k
        buf.append(line)
    if buf:
        out.append((kind, "\n".join(buf)))
    return out


class _PageChunker:
    def __init__(self, ntok: Callable[[str], int], size: int):
        self.ntok, self.size = ntok, size

    def split_table(self, text: str, budget: int) -> List[str]:
        if self.ntok(text) <= budget:
            return [text]
        lines = text.split("\n")
        hdr, rows = (lines[:2], lines[2:]) if len(lines) > 2 and SEP.match(lines[1]) else ([], lines)
        header_tokens = self.ntok("\n".join(hdr))
        pieces: List[str] = []
        cur: List[str] = []
        used = header_tokens
        for row in rows:
            row_tokens = self.ntok(row) + 1
            if cur and used + row_tokens > budget:
                pieces.append("\n".join(hdr + cur))
                cur, used = [], header_tokens
            cur.append(row)
            used += row_tokens
        if cur:
            pieces.append("\n".join(hdr + cur))
        return pieces

    def split_para(self, text: str, budget: int) -> List[str]:
        if self.ntok(text) <= budget:
            return [text]
        pieces: List[str] = []
        cur: List[str] = []
        used = 0
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sentence_tokens = self.ntok(sentence) + 1
            if cur and used + sentence_tokens > budget:
                pieces.append(" ".join(cur))
                cur, used = [], 0
            cur.append(sentence)
            used += sentence_tokens
        if cur:
            pieces.append(" ".join(cur))
        return pieces

    def page_units(self, md: str, carry: List[str], sec: str):
        """-> (units, carried headings, section). Headings glue forward; a short paragraph right before a table and
        footnote paragraphs right after it glue to the table. unit = dict(text, tokens, kind, sec, ttl)."""
        units: List[Dict[str, Any]] = []
        heads = list(carry)
        prev: Optional[Dict[str, Any]] = None
        for kind, text in parse_blocks(md):
            if kind == "h":
                heads.append(text)
                sec = re.sub(r"^#+\s*", "", text).strip() or sec
                continue
            head = "\n".join(heads)
            heads = []
            budget = self.size - self.ntok(head)
            pieces = self.split_table(text, budget) if kind == "t" else self.split_para(text, budget)
            title = re.sub(r"^#+\s*", "", head.split("\n")[-1]) if (kind == "t" and head) else ""
            for i, piece in enumerate(pieces):
                t = (head + "\n\n" + piece) if (i == 0 and head) else piece
                unit = dict(text=t, tokens=self.ntok(t), kind=kind, sec=sec, ttl=title if kind == "t" else "")
                if (kind == "t" and prev and prev["kind"] == "p" and prev["tokens"] <= INTRO_MAX_TOKENS
                        and not head and i == 0 and prev["tokens"] + unit["tokens"] <= self.size):
                    parts = prev["text"].split("\n\n")
                    heading = next((x for x in parts if x.startswith("#")), None)
                    intro = " ".join(x for x in parts if not x.startswith("#"))
                    prev["ttl"] = (re.sub(r"^#+\s*", "", heading.split("\n")[-1]).strip() if heading
                                   else re.sub(r"\s+", " ", intro).strip()[:140])
                    prev["text"] += "\n\n" + t
                    prev["tokens"] += unit["tokens"] + 1
                    prev["kind"] = "t"
                    continue
                if (kind == "p" and prev and prev["kind"] == "t" and FOOT.match(text) and not head
                        and prev["tokens"] + unit["tokens"] <= self.size):
                    prev["text"] += "\n\n" + t
                    prev["tokens"] += unit["tokens"] + 1
                    continue
                units.append(unit)
                prev = unit
        return units, heads, sec

    def pack(self, units: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        chunks: List[List[Dict[str, Any]]] = []
        cur: List[Dict[str, Any]] = []
        used = 0
        for unit in units:
            if cur and used + unit["tokens"] > self.size:
                chunks.append(cur)
                cur, used = [], 0
            cur.append(unit)
            used += unit["tokens"]
        if cur:
            chunks.append(cur)
        if len(chunks) >= 2:
            tail = sum(u["tokens"] for u in chunks[-1])
            before = sum(u["tokens"] for u in chunks[-2])
            if tail < MIN_TAIL_TOKENS and before + tail <= self.size * 1.25:
                last = chunks.pop()
                chunks[-1] += last
        return chunks


class FinancialChunkerService:
    """Chunks parsed pages (Markdown) while preserving tables, headers, footnotes and page provenance."""

    @staticmethod
    def chunk_document(
        notebook_id: str,
        document_id: str,
        pages_data: List[Dict[str, Any]],
        count_tokens: Optional[Callable[[str], int]] = None,
        size: Optional[int] = None,
    ) -> List[ChunkDocument]:
        chunker = _PageChunker(count_tokens or bge_m3_token_counter(), size or settings.CHUNK_TOKENS)
        chunks: List[ChunkDocument] = []
        carry: List[str] = []
        section = ""
        for page in sorted(pages_data, key=lambda p: p["page_number"]):
            markdown = page["text"]
            if not markdown.strip():
                continue
            units, carry, section = chunker.page_units(markdown, carry, section)
            for group in chunker.pack(units):
                text = "\n\n".join(u["text"] for u in group)
                table = next((u for u in group if u["kind"] == "t"), None)
                unit_match = UNIT.search(table["text"]) if table else None
                tokens = chunker.ntok(text)
                chunks.append(
                    ChunkDocument(
                        chunk_id=f"{document_id}_chk_{len(chunks) + 1:04d}",
                        notebook_id=notebook_id,
                        document_id=document_id,
                        page=page["page_number"],
                        section=group[0]["sec"] or None,
                        chunk_type="table" if table else "text",
                        text_type="financial_statement" if table else "narrative",
                        content=text,
                        token_count=tokens,
                        table_metadata=(
                            {"title": table["ttl"], "unit": f"in {unit_match.group(1).lower()}" if unit_match else ""}
                            if table else None
                        ),
                        page_tokens={str(page["page_number"]): tokens},
                    )
                )
        return chunks
