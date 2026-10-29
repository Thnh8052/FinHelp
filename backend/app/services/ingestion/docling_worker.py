"""Subprocess worker: PDF -> Docling (TableFormer ACCURATE, no OCR) -> research postprocess -> pages.json.

    python -X utf8 -m app.services.ingestion.docling_worker <pdf> <work_dir>     # one file, then exit
    python -X utf8 -m app.services.ingestion.docling_worker --serve              # several files, models loaded once

It runs in its own process because Docling is heavy and unreliable on a 4 GB laptop GPU (CUDA errors, OOM); the API
process only waits for it. Output: <work_dir>/pages.json = [{"page_number": n, "text": "<markdown>"}, ...].
--serve reads one JSON request per line on stdin ({"pdf", "work"}) and answers one JSON line on stdout
({"ok", "pages", "convert_s", "postprocess_s"} or {"ok": false, "error"}); the converter (layout + TableFormer models) is built once,
so only the first file pays the model load. Docling's own logging goes to stderr.
"""
import json
import os
import sys
import time
from pathlib import Path

from app.core.config import settings
from app.services.ingestion.postprocess import process as postprocess


def build_converter():
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    options.accelerator_options = AcceleratorOptions(device=settings.DOCLING_DEVICE)
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})


def convert(converter, pdf: Path, raw_dir: Path) -> None:
    result = converter.convert(str(pdf), raises_on_error=False)
    document = result.document
    (raw_dir / "pages").mkdir(parents=True, exist_ok=True)
    document.save_as_json(raw_dir / "docling.json")
    for page_no in sorted(document.pages):
        (raw_dir / "pages" / f"page_{page_no:03d}.md").write_text(
            document.export_to_markdown(page_no=page_no), encoding="utf-8"
        )


def parse(converter, pdf: Path, work: Path) -> dict:
    t0 = time.time()
    raw_dir = work / "raw" / pdf.stem  # postprocess finds the PDF as <PDF_DIR>/<raw_dir.name>.pdf
    convert(converter, pdf, raw_dir)
    t1 = time.time()
    postprocess(raw_dir, pdf.parent, work / "fixed")
    pages = [
        {"page_number": int(p.stem.split("_")[1]), "text": p.read_text(encoding="utf-8")}
        for p in sorted((work / "fixed" / pdf.stem / "pages").glob("page_*.md"))
    ]
    (work / "pages.json").write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "pages": len(pages), "convert_s": round(t1 - t0, 2), "postprocess_s": round(time.time() - t1, 2)}


def main(pdf: Path, work: Path) -> None:
    started = time.time()
    out = parse(build_converter(), pdf, work)
    print(f"docling done: {out['pages']} pages in {time.time() - started:.0f}s", flush=True)


def serve() -> None:
    # The answer channel is a private copy of the real stdout; file descriptor 1 itself now points at stderr, so nothing else (the
    # app logger bound its handler to stdout at import, libraries print, C extensions write fd 1) can corrupt it.
    sys.stdout.flush()
    answers = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    t0 = time.time()
    converter = build_converter()
    print(json.dumps({"ready": True, "init_s": round(time.time() - t0, 2)}), file=answers, flush=True)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            out = parse(converter, Path(req["pdf"]), Path(req["work"]))
        except Exception as exc:  # one bad file must not end the session
            out = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        print(json.dumps(out), file=answers, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--serve"]:
        serve()
    else:
        main(Path(sys.argv[1]), Path(sys.argv[2]))
