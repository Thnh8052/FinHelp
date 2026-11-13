import React, { useState, useEffect, useRef } from "react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { useLanguage } from "../../context/LanguageContext";
import { CitationItem } from "../../types/chat";
import { DocumentRecord } from "../../types/notebook";
import { documentService } from "../../services/documents";
import { bandsFor, figureLines, locateExcerpt, type Box, type PageItem } from "./locateExcerpt";
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
    // Read here, not from the observer: it reports nothing until the page is painted. 10: the panel's padding and the canvas border
    const available = (viewportRef.current?.clientWidth ?? 0) - 10;
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

  if (!currentDoc) {
    return (
      <div className="pdf-viewer-empty-state">
        <div className="pdf-empty-icon-box">
          <FileTextIcon size={24} color="var(--text-dim, #94a3b8)" />
        </div>
        <p className="pdf-empty-title">{t.sourceViewer.noFilingSelected}</p>
        <p className="pdf-empty-sub">{t.sourceViewer.noFilingSubtext}</p>
      </div>
    );
  }

  const pdfUrl = pdfObjectUrl ? `${pdfObjectUrl}#page=${currentPage}` : null;
  // An excerpt from a report deleted since the answer: its text is kept with the message, but no open report may claim it
  const citationGone = !!activeCitation?.document_id && !documents.some((d) => d.document_id === activeCitation.document_id);

  return (
    <div className="pdf-split-viewer-container">
      {/* 1. PDF Toolbar */}
      <div className="pdf-viewer-toolbar">
        {/* Document Tab Bar */}
        <div className="pdf-docs-tab-bar scrollbar-slim">
          <span className="pdf-tab-label">{t.sourceViewer.filingsLabel}</span>
          {documents.map((doc) => {
            const isTabActive = doc.document_id === currentDoc.document_id;
            return (
              <button
                key={doc.document_id}
                type="button"
                onClick={() => {
                  onSelectDoc(doc.document_id);
                  onClearCitation();
                }}
                className={`pdf-doc-tab-btn ${isTabActive ? "active" : ""}`}
                title={doc.file_name}
              >
                <FileTextIcon size={12} color={isTabActive ? "#ffffff" : "var(--text-dim, #94a3b8)"} />
                <span className="pdf-tab-text">{doc.file_name}</span>
              </button>
            );
          })}
        </div>

        {/* Navigation & Zoom Controls */}
        <div className="pdf-nav-controls">
          <button
            type="button"
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            className="pdf-page-btn"
            title={t.sourceViewer.prevPage}
          >
            <ChevronLeftIcon size={13} />
          </button>

          <span className="pdf-page-indicator">
            Page {currentPage} of {totalPages}
          </span>

          <button
            type="button"
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            className="pdf-page-btn"
            title={t.sourceViewer.nextPage}
          >
            <ChevronRightIcon size={13} />
          </button>

          <div className="pdf-toolbar-sep" />

          {/* Zoom In / Out / Fit Width */}
          <button
            type="button"
            onClick={handleZoomOut}
            className="pdf-page-btn"
            title={t.sourceViewer.zoomOutPct}
          >
            <ZoomOutIcon size={13} />
          </button>

          <button
            type="button"
            onClick={handleToggleFitWidth}
            className={`pdf-zoom-indicator ${isFitWidth ? "active" : ""}`}
            title={isFitWidth ? t.sourceViewer.fitWidthClick : t.sourceViewer.zoomPctClick.replace("{zoom}", String(zoomLevel))}
          >
            <FitWidthIcon size={12} />
            <span>{isFitWidth ? t.sourceViewer.fit : `${zoomLevel}%`}</span>
          </button>

          <button
            type="button"
            onClick={handleZoomIn}
            className="pdf-page-btn"
            title={t.sourceViewer.zoomInPct}
          >
            <ZoomInIcon size={13} />
          </button>

          <div className="pdf-toolbar-sep" />

          {/* Open in new tab */}
          {pdfUrl && (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="pdf-page-btn"
              title={t.sourceViewer.openPageNewTab.replace("{page}", String(currentPage))}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
            </a>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="pdf-close-btn"
              title={t.sourceViewer.closeViewer}
            >
              <CloseIcon size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 2. Only when there is something to say: the cited report is gone, or the page has nothing to mark (a scan, or turned sideways). Otherwise the PDF alone, with the marks on it. */}
      {activeCitation && (citationGone || (citationHere && marks && marks.page === currentPage && marks.boxes.length + marks.figures.length === 0)) && (
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
    </div>
  );
};
