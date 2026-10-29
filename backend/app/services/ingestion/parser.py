import asyncio
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.exceptions import IngestionError
from app.core.logging import logger


def _pymupdf_pages(pdf_path: Path) -> List[Dict[str, Any]]:
    """Fast parse: page text in reading order with real tables rendered as Markdown (PyMuPDF find_tables).

    Not the measured configuration: Docling + postprocess is more accurate on financial tables."""
    import fitz  # PyMuPDF

    pages: List[Dict[str, Any]] = []
    with fitz.open(str(pdf_path)) as doc:
        for index, page in enumerate(doc, 1):
            try:
                tables = page.find_tables().tables
            except Exception:
                tables = []
            boxes = [fitz.Rect(t.bbox) for t in tables]
            parts: List[Tuple[float, str]] = []
            for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
                rect = fitz.Rect(x0, y0, x1, y1)
                area = rect.get_area()
                if area and any((rect & box).get_area() / area > 0.5 for box in boxes):
                    continue  # text that belongs to a table is emitted by the table itself
                if text.strip():
                    parts.append((y0, text.strip()))
            parts += [(t.bbox[1], t.to_markdown().strip()) for t in tables]
            parts.sort(key=lambda p: p[0])
            pages.append({"page_number": index, "text": "\n\n".join(p[1] for p in parts if p[1]), "tables": []})
    return pages


def _docling_pages(pdf_path: Path, work_dir: Path) -> List[Dict[str, Any]]:
    """Run the Docling worker in a subprocess (retrying, since the laptop GPU is flaky)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    log_file = work_dir / "docling.log"
    command = [sys.executable, "-X", "utf8", "-m", "app.services.ingestion.docling_worker", str(pdf_path), str(work_dir)]
    for attempt in range(1, settings.DOCLING_RETRIES + 2):
        try:
            with open(log_file, "a", encoding="utf-8") as log:
                subprocess.run(
                    command, cwd=settings.BASE_DIR, stdout=log, stderr=subprocess.STDOUT,
                    timeout=settings.DOCLING_TIMEOUT_SECONDS, check=True,
                )
            return json.loads((work_dir / "pages.json").read_text(encoding="utf-8"))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            logger.warning(f"Docling attempt {attempt} failed ({type(exc).__name__}); see {log_file}")
    raise IngestionError("Docling không xử lý được tài liệu sau các lần thử.")


class DoclingSession:
    """One Docling worker process (`docling_worker --serve`) kept alive for a batch of files: the layout and TableFormer models load
    once instead of once a file. Blocking methods (call them through asyncio.to_thread). A crash, an error answer or a timeout
    closes the process; the file is retried once in a fresh process, then the caller falls back to PyMuPDF."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.proc: Optional[subprocess.Popen] = None
        self.init_s: Optional[float] = None  # seconds the last start took (converter + models)

    def _start(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        self.proc = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-m", "app.services.ingestion.docling_worker", "--serve"], cwd=settings.BASE_DIR,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(self.log_file, "a", encoding="utf-8"),
            text=True, encoding="utf-8", bufsize=1,
        )
        self._answer()
        self.init_s = round(time.perf_counter() - t0, 2)

    def _answer(self) -> Dict[str, Any]:
        """The worker's next JSON answer line (any other line on the channel is skipped and logged)."""
        got: Dict[str, Any] = {}

        def read() -> None:
            for line in self.proc.stdout:
                line = line.strip()
                if line.startswith("{"):
                    try:
                        got["answer"] = json.loads(line)
                        return
                    except ValueError:
                        pass
                if line:
                    logger.debug(f"Docling worker stdout (not an answer): {line[:160]}")

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(settings.DOCLING_TIMEOUT_SECONDS)
        if reader.is_alive() or "answer" not in got:
            self.close()
            raise IngestionError("Docling worker did not answer.")
        return got["answer"]

    def parse(self, pdf_path: Path, work_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """(pages, {"convert_s", "postprocess_s", "start_s"}) for one file."""
        work_dir.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, settings.DOCLING_RETRIES + 2):
            started = None
            try:
                if self.proc is None or self.proc.poll() is not None:
                    self._start()
                    started = self.init_s
                self.proc.stdin.write(json.dumps({"pdf": str(pdf_path), "work": str(work_dir)}) + "\n")
                self.proc.stdin.flush()
                out = self._answer()
                if out.get("ok"):
                    pages = json.loads((work_dir / "pages.json").read_text(encoding="utf-8"))
                    return pages, {"convert_s": out.get("convert_s"), "postprocess_s": out.get("postprocess_s"), "start_s": started or 0.0}
                logger.warning(f"Docling attempt {attempt} on {pdf_path.name} failed: {out.get('error')}")
            except (OSError, ValueError, IngestionError) as exc:
                logger.warning(f"Docling attempt {attempt} on {pdf_path.name} failed ({type(exc).__name__}); see {self.log_file}")
            self.close()
        raise IngestionError("Docling không xử lý được tài liệu sau các lần thử.")

    def close(self) -> None:
        """End the worker (its GPU memory goes back to the embedding and reranker models)."""
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            proc.stdin.close()
            proc.wait(timeout=20)
        except Exception:
            proc.kill()


class PDFParserService:
    """Parses a financial report PDF into per-page Markdown."""

    @staticmethod
    async def extract_pages(pdf_path: Path, document_id: str = "doc", session: Optional[DoclingSession] = None,
                            info: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], str]:
        """-> (pages, engine_used). pages = [{"page_number", "text" (Markdown), "tables"}]. A Docling failure falls back to
        PyMuPDF and says so in the returned engine name instead of failing silently. `session`: the batch's Docling worker
        (models already loaded); `info` receives its timings (convert_s, postprocess_s, start_s)."""
        engine = settings.PARSER_ENGINE
        if engine == "docling":
            work_dir = settings.ARTIFACTS_STORAGE_DIR / document_id
            try:
                if session is not None:
                    pages, timing = await asyncio.to_thread(session.parse, pdf_path, work_dir)
                    if info is not None:
                        info.update(timing)
                else:
                    pages = await asyncio.to_thread(_docling_pages, pdf_path, work_dir)
                return [{**p, "tables": []} for p in pages], "docling"
            except IngestionError as exc:
                logger.warning(f"{exc} Falling back to the PyMuPDF parser.")
                engine = "pymupdf_fallback"
            finally:
                shutil.rmtree(work_dir / "raw", ignore_errors=True)  # keep pages.json + log, drop the big raw dump
        logger.info(f"Parsing PDF {pdf_path.name} with PyMuPDF...")
        return await asyncio.to_thread(_pymupdf_pages, pdf_path), engine
