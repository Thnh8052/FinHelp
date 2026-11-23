import React, { useState, useEffect, useRef } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { useLanguage } from "../../context/LanguageContext";
import { CitationItem } from "../../types/chat";
import { DocumentRecord, documentLabel } from "../../types/notebook";
import { documentService } from "../../services/documents";
import { bandsFor, figureLines, locateExcerpt, type Box, type PageItem } from "./locateExcerpt";
import { ChevronDown, ExternalLink, Maximize2, Minimize2 } from "lucide-react";
import {
  FileTextIcon,
  CloseIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ZoomInIcon,
  ZoomOutIcon,
  FitWidthIcon,
} from "../common/Icons";
import "./notebook.css";

/** pdf.js is fetched the first time a PDF opens, so the rest of the app does not carry it. */
async function loadPdfJs() {
  const [pdfjs, worker] = await Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?url")]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  return pdfjs;
}

interface SourceViewerProps {
  documents: DocumentRecord[];
  activeDocId: string | null;
  onSelectDoc: (docId: string) => void;
  activeCitation: CitationItem | null;
  onClearCitation: () => void;
  onClose?: () => void;
}

/**
 * Trình đọc BCTC PDF Gốc Đối Chiếu (SEC Insights True Split-View)
 * Mở song song ở panel bên phải (~50-55% màn hình)
 * Tự động chuyển file, nhảy đúng trang và chuẩn hóa bảng Markdown khi người dùng click vào citation [1] Trang 12.
 */
export const SourceViewer: React.FC<SourceViewerProps> = ({
  documents,
  activeDocId,
  onSelectDoc,
  activeCitation,
  onClearCitation,
  onClose,
}) => {
  const { t } = useLanguage();
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [isFitWidth, setIsFitWidth] = useState<boolean>(true);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [pdfFailed, setPdfFailed] = useState(false);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [viewportWidth, setViewportWidth] = useState(0);
  // How the page was last drawn (the scale the lines of the excerpt are placed with) and the lines found for the active citation
  const [pageView, setPageView] = useState<{ page: number; transform: number[]; width: number; rotated: boolean } | null>(null);
  const [marks, setMarks] = useState<{ page: number; boxes: Box[]; figures: Box[]; found: number } | null>(null); // boxes: lines of the excerpt; figures: lines with the numbers the answer states
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFull, setIsFull] = useState(false);
  const [pageDraft, setPageDraft] = useState<string | null>(null); // what is typed in the page box until Enter or leaving it
  const pageText = useRef<Map<number, PageItem[]>>(new Map()); // the text pdf.js reads from each page of the open report, read once

  const handleZoomIn = () => {
    setIsFitWidth(false);
    setZoomLevel((prev) => Math.min(prev + 15, 250));
  };

  const handleZoomOut = () => {
    setIsFitWidth(false);
    setZoomLevel((prev) => Math.max(prev - 15, 50));
  };

  const handleToggleFitWidth = () => {
    if (isFitWidth) {
      setIsFitWidth(false);
      setZoomLevel(100);
    } else {
      setIsFitWidth(true);
    }
  };

  // Tìm tài liệu đang được xem
  const currentDoc =
    documents.find((d) => d.document_id === activeDocId) ||
    documents[0] ||
    null;

  const totalPages = pdfDoc?.numPages || currentDoc?.page_count || 1;
  const documentId = currentDoc?.document_id;

  // PDF được tải kèm header đăng nhập (token không bao giờ nằm trong URL), mở một lần bằng pdf.js; lật trang chỉ vẽ lại trang đó
  useEffect(() => {
    if (!documentId) return;
    let replaced = false;
    let objectUrl: string | null = null;
    let loading: { destroy(): Promise<void> } | null = null;
    setPdfObjectUrl(null);
    setPdfDoc(null);
    setPdfFailed(false);
    setPageView(null);
    pageText.current = new Map();
    Promise.all([documentService.getFile(documentId), loadPdfJs()])
      .then(async ([blob, pdfjs]) => {
        if (replaced) return;
        objectUrl = URL.createObjectURL(blob); // only for "open in a new tab"
        setPdfObjectUrl(objectUrl);
        const task = pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) });
        loading = task;
        if (replaced) return void task.destroy();
        const doc = await task.promise;
        if (!replaced) setPdfDoc(doc);
      })
      .catch(() => {
        if (!replaced) setPdfFailed(true);
      });
    return () => {
      replaced = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      loading?.destroy(); // frees the worker and the document
    };
  }, [documentId]);

  // Fit-width follows the panel's width: a resize draws the page again
  const hasDoc = currentDoc !== null;
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setViewportWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasDoc]);

  // The page is drawn off screen and copied in when done: the old page stays visible meanwhile, so turning a page does not flash
  useEffect(() => {
    const canvas = canvasRef.current;
    // Read here, not from the observer: it reports nothing until the page is painted. 34: the panel's padding (2 x 16) and the canvas border
    const available = (viewportRef.current?.clientWidth ?? 0) - 34;
    if (!pdfDoc || !canvas || (isFitWidth && available <= 0)) return;
    let cancelled = false;
    let task: RenderTask | null = null;
    (async () => {
      const page = await pdfDoc.getPage(Math.min(Math.max(currentPage, 1), pdfDoc.numPages));
      if (cancelled) return;
      const natural = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: isFitWidth ? available / natural.width : zoomLevel / 100 });
      const ratio = window.devicePixelRatio || 1;
      const offscreen = document.createElement("canvas");
      offscreen.width = Math.floor(viewport.width * ratio);
      offscreen.height = Math.floor(viewport.height * ratio);
      task = page.render({ canvas: offscreen, viewport, transform: ratio === 1 ? undefined : [ratio, 0, 0, ratio, 0, 0] });
      await task.promise;
      if (cancelled) return;
      canvas.width = offscreen.width;
      canvas.height = offscreen.height;
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;
      canvas.getContext("2d")?.drawImage(offscreen, 0, 0);
      setPageView({ page: page.pageNumber, transform: viewport.transform, width: viewport.width, rotated: page.rotate % 360 !== 0 });
    })().catch((err) => {
      if (!cancelled && err?.name !== "RenderingCancelledException") setPdfFailed(true);
    });
    return () => {
      cancelled = true;
      task?.cancel();
    };
  }, [pdfDoc, currentPage, isFitWidth, zoomLevel, viewportWidth]);

  // Khi có citation mới: tự động nhảy sang trang của citation
  useEffect(() => {
    if (activeCitation) {
      if (activeCitation.document_id === currentDoc?.document_id) {
        if (activeCitation.page && activeCitation.page > 0) {
          setCurrentPage(activeCitation.page);
        }
      }
    }
  }, [activeCitation, currentDoc?.document_id]);

  // F9: the lines of the cited excerpt are looked for in the text of the page the citation points at, and marked once the page is drawn.
  // A page without text (a scan) or turned sideways has nothing to mark: the banner says so and the page jump still works.
  const citationHere = !!activeCitation && !!currentDoc && activeCitation.document_id === currentDoc.document_id && activeCitation.page === currentPage;
  useEffect(() => {
    if (!pdfDoc || !pageView || pageView.page !== currentPage || !activeCitation || !citationHere) {
      setMarks(null);
      return;
    }
    if (pageView.rotated) {
      setMarks({ page: currentPage, boxes: [], figures: [], found: 0 });
      return;
    }
    let cancelled = false;
    (async () => {
      let items = pageText.current.get(currentPage);
      if (!items) {
        const content = await (await pdfDoc.getPage(currentPage)).getTextContent();
        items = (content.items as Array<{ str?: string; transform?: number[]; width?: number }>)
          .filter((i) => typeof i.str === "string" && Array.isArray(i.transform))
          .map((i) => ({ str: i.str as string, transform: i.transform as number[], width: i.width ?? 0 }));
        pageText.current.set(currentPage, items);
      }
      if (cancelled) return;
      const located = locateExcerpt(activeCitation.snippet, items);
      const stated = figureLines(items, activeCitation.figures ?? []); // the lines of the numbers the answer states: the evidence itself, marked stronger
      setMarks({
        page: currentPage,
        boxes: bandsFor(items, located.items, pageView.transform, pageView.width),
        figures: bandsFor(items, stated, pageView.transform, pageView.width),
        found: located.found + stated.length,
      });
    })().catch(() => {
      if (!cancelled) setMarks({ page: currentPage, boxes: [], figures: [], found: 0 });
    });
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pageView, currentPage, activeCitation, citationHere]);

  // A page (or report) is read from its top: turning to it must not keep the position of the page before. When the page holds the cited lines,
  // the effect below brings the first of them into view once they are marked.
  useEffect(() => {
    viewportRef.current?.scrollTo({ top: 0 });
  }, [currentPage, currentDoc?.document_id]);

  // The first marked line is brought into view (a page is taller than the panel)
  useEffect(() => {
    const first = marks && marks.page === currentPage ? marks.figures[0] ?? marks.boxes[0] : undefined; // the stated figure first, else the first line of the excerpt
    const container = viewportRef.current;
    const wrap = wrapRef.current;
    if (!first || !container || !wrap) return;
    const top = wrap.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop + first.top - container.clientHeight / 3;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    container.scrollTo({ top: Math.max(0, top), behavior: reduced ? "auto" : "smooth" });
  }, [marks, currentPage]);

  const handlePrevPage = () => {
    if (currentPage > 1) setCurrentPage((prev) => prev - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) setCurrentPage((prev) => prev + 1);
  };

  // The page box: a typed number is kept inside 1..totalPages; anything else is dropped
  const commitPageDraft = () => {
    const n = parseInt(pageDraft ?? "", 10);
    if (Number.isFinite(n)) setCurrentPage(Math.min(Math.max(n, 1), totalPages));
    setPageDraft(null);
  };

  // Full screen is the browser's own, on the whole panel; Esc leaves it
  useEffect(() => {
    const onChange = () => setIsFull(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);
  const toggleFullscreen = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else containerRef.current?.requestFullscreen().catch(() => undefined); // a browser or frame that refuses full screen leaves the panel as it is
  };
  const closeViewer = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    onClose?.();
  };

  if (!currentDoc) {
    return (
      <div className="pdf-viewer-empty-state">
        <div className="pdf-empty-icon-box">
          <FileTextIcon size={24} color="var(--text-dim)" />
        </div>
        <p className="pdf-empty-title">{t.sourceViewer.noFilingSelected}</p>
        <p className="pdf-empty-sub">{t.sourceViewer.noFilingSubtext}</p>
      </div>
    );
  }

  const pdfUrl = pdfObjectUrl ? `${pdfObjectUrl}#page=${currentPage}` : null;
  // Under the name: what the catalog knows about the report (company, type, year), then its length
  const label = documentLabel(currentDoc);
  const fileMeta = [label !== currentDoc.file_name ? label : "", t.sourceViewer.pagesN.replace("{n}", String(totalPages))].filter(Boolean).join(" · ");
  // An excerpt from a report deleted since the answer: its text is kept with the message, but no open report may claim it
  const citationGone = !!activeCitation?.document_id && !documents.some((d) => d.document_id === activeCitation.document_id);

  return (
    <div className="pdf-split-viewer-container" ref={containerRef}>
      {/* 1. Title, the report chooser, close */}
      <div className="pdf-head">
        <h2 className="pdf-head-title">{t.sourceViewer.previewTitle}</h2>
        <label className="pdf-select">
          <span>{t.sourceViewer.allReports.replace("{n}", String(documents.length))}</span>
          <ChevronDown size={12} aria-hidden />
          <select
            value={currentDoc.document_id}
            aria-label={t.sourceViewer.chooseReport}
            onChange={(e) => {
              onSelectDoc(e.target.value);
              onClearCitation();
            }}
          >
            {documents.map((doc) => (
              <option key={doc.document_id} value={doc.document_id}>{doc.file_name}</option>
            ))}
          </select>
        </label>
        <span className="pdf-head-spacer" />
        {onClose && (
          <button type="button" onClick={closeViewer} className="pdf-close-btn" title={t.sourceViewer.closeViewer} aria-label={t.sourceViewer.closeViewer}>
            <CloseIcon size={18} />
          </button>
        )}
      </div>

      {/* The open report */}
      <div className="pdf-file">
        <FileTextIcon size={22} color="var(--accent-text)" />
        <div className="pdf-file-text">
          <b className="pdf-file-name" title={currentDoc.file_name}>{currentDoc.file_name}</b>
          <small>{fileMeta}</small>
        </div>
        {pdfUrl && (
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="pdf-icon-btn"
            title={t.sourceViewer.openPageNewTab.replace("{page}", String(currentPage))}
            aria-label={t.sourceViewer.openPageNewTab.replace("{page}", String(currentPage))}
          >
            <ExternalLink size={18} aria-hidden />
          </a>
        )}
      </div>

      {/* Page number, zoom, full screen */}
      <div className="pdf-pager">
        <button type="button" onClick={handlePrevPage} disabled={currentPage <= 1} className="pdf-icon-btn" title={t.sourceViewer.prevPage} aria-label={t.sourceViewer.prevPage}>
          <ChevronLeftIcon size={16} />
        </button>
        <input
          className="pdf-page-input"
          inputMode="numeric"
          aria-label={t.sourceViewer.pageNumber}
          value={pageDraft ?? String(currentPage)}
          onFocus={(e) => e.target.select()}
          onChange={(e) => setPageDraft(e.target.value.replace(/\D/g, ""))}
          onBlur={commitPageDraft}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
        />
        <span>/ {totalPages}</span>
        <button type="button" onClick={handleNextPage} disabled={currentPage >= totalPages} className="pdf-icon-btn" title={t.sourceViewer.nextPage} aria-label={t.sourceViewer.nextPage}>
          <ChevronRightIcon size={16} />
        </button>

        <span className="pdf-pager-spacer" />

        <button type="button" onClick={handleZoomOut} className="pdf-icon-btn" title={t.sourceViewer.zoomOutPct} aria-label={t.sourceViewer.zoomOutPct}>
          <ZoomOutIcon size={16} />
        </button>
        <button
          type="button"
          onClick={handleToggleFitWidth}
          className={`pdf-zoom-indicator ${isFitWidth ? "active" : ""}`}
          title={isFitWidth ? t.sourceViewer.fitWidthClick : t.sourceViewer.zoomPctClick.replace("{zoom}", String(zoomLevel))}
        >
          <FitWidthIcon size={13} />
          <span>{isFitWidth ? t.sourceViewer.fit : `${zoomLevel}%`}</span>
        </button>
        <button type="button" onClick={handleZoomIn} className="pdf-icon-btn" title={t.sourceViewer.zoomInPct} aria-label={t.sourceViewer.zoomInPct}>
          <ZoomInIcon size={16} />
        </button>
        {document.fullscreenEnabled && (
          <button
            type="button"
            onClick={toggleFullscreen}
            className="pdf-icon-btn"
            title={isFull ? t.sourceViewer.exitFullscreen : t.sourceViewer.fullscreen}
            aria-label={isFull ? t.sourceViewer.exitFullscreen : t.sourceViewer.fullscreen}
          >
            {isFull ? <Minimize2 size={16} aria-hidden /> : <Maximize2 size={16} aria-hidden />}
          </button>
        )}
      </div>

      {/* The citation that opened this page, once its lines are marked on it */}
      {activeCitation && citationHere && marks && marks.page === currentPage && marks.boxes.length + marks.figures.length > 0 && (
        <div className="pdf-context-bar" role="status">
          <FileTextIcon size={15} />
          <span>{t.workspace.pageLabel} {currentPage} · {t.sourceViewer.highlightedInSource}</span>
        </div>
      )}

      {/* 2. Only when there is something to say: the cited report is gone, or the page has nothing to mark (a scan, or turned sideways). Otherwise the PDF alone, with the marks on it.
          A page opened from the document card (a page to check) has no excerpt to mark: nothing to say. */}
      {activeCitation && (citationGone || (!!activeCitation.snippet && citationHere && marks && marks.page === currentPage && marks.boxes.length + marks.figures.length === 0)) && (
        <div className="pdf-evidence-banner">
          <div className="pdf-evidence-header">
            <p className="pdf-evidence-note" role="status">
              {citationGone ? t.sourceViewer.citationSourceRemoved.replace("{page}", String(activeCitation.page)) : t.sourceViewer.highlightNotFound}
            </p>
            <button onClick={onClearCitation} className="pdf-clear-cite-btn" title={t.sourceViewer.clearHighlight}>
              <CloseIcon size={11} />
            </button>
          </div>
        </div>
      )}

      {/* 3. Original PDF Page Viewport */}
      <div className="pdf-display-viewport scrollbar-slim" ref={viewportRef}>
        {pdfDoc && !pdfFailed ? (
          <div className="pdf-page-wrap" ref={wrapRef}>
            <canvas
              ref={canvasRef}
              role="img"
              aria-label={`${t.sourceViewer.reportTitle.replace("{name}", currentDoc.file_name)}, ${t.sourceViewer.page} ${currentPage}`}
              className="pdf-render-canvas"
            />
            {citationHere && marks && marks.page === currentPage && (
              <div className="pdf-highlight-layer" aria-hidden="true">
                {marks.boxes.map((b, i) => (
                  <div key={`e${i}`} className="pdf-highlight-box" style={{ left: b.left - 2, top: b.top - 1, width: b.width + 4, height: b.height + 2 }} />
                ))}
                {marks.figures.map((b, i) => (
                  <div key={`f${i}`} className="pdf-highlight-box strong" style={{ left: b.left - 2, top: b.top - 1, width: b.width + 4, height: b.height + 2 }} />
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="pdf-viewer-empty-state">
            <p className="pdf-empty-sub" role="status">{pdfFailed ? t.sourceViewer.pdfFailed : t.sourceViewer.pdfLoading}</p>
          </div>
        )}
      </div>

      <div className="pdf-note">
        <FileTextIcon size={16} color="var(--accent-text)" />
        <div>
          <b>{t.sourceViewer.contextTitle}</b>
          {t.sourceViewer.contextText}
        </div>
      </div>
    </div>
  );
};
