import React, { useState, useEffect } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { CitationItem } from "../../types/chat";
import { DocumentRecord } from "../../types/notebook";
import { documentService } from "../../services/documents";
import { MarkdownRenderer } from "../chat/MarkdownRenderer";
import {
  FileTextIcon,
  CloseIcon,
  CheckIcon,
  CheckShieldIcon,
  CopyIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ZoomInIcon,
  ZoomOutIcon,
  FitWidthIcon,
} from "../common/Icons";
import "./notebook.css";

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
  const [copied, setCopied] = useState(false);
  const [highlightPulse, setHighlightPulse] = useState(false);
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [isFitWidth, setIsFitWidth] = useState<boolean>(true);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [pdfFailed, setPdfFailed] = useState(false);

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

  const totalPages = currentDoc?.page_count || 1;
  const documentId = currentDoc?.document_id;

  // PDF được tải kèm header đăng nhập rồi mở bằng địa chỉ blob: token không bao giờ nằm trong URL của iframe
  useEffect(() => {
    if (!documentId) return;
    let replaced = false;
    let objectUrl: string | null = null;
    setPdfObjectUrl(null);
    setPdfFailed(false);
    documentService.getFile(documentId).then(
      (blob) => {
        if (replaced) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfObjectUrl(objectUrl);
      },
      () => {
        if (!replaced) setPdfFailed(true);
      }
    );
    return () => {
      replaced = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  // Khi có citation mới: Tự động nhảy sang trang của citation và kích hoạt hiệu ứng highlight
  useEffect(() => {
    if (activeCitation) {
      if (activeCitation.document_id === currentDoc?.document_id) {
        if (activeCitation.page && activeCitation.page > 0) {
          setCurrentPage(activeCitation.page);
        }
        setHighlightPulse(true);
        const timer = setTimeout(() => setHighlightPulse(false), 3500);
        return () => clearTimeout(timer);
      }
    }
  }, [activeCitation, currentDoc?.document_id]);

  const handleCopy = () => {
    if (!activeCitation?.snippet) return;
    navigator.clipboard.writeText(activeCitation.snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
            title="Previous page"
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
            title="Next page"
          >
            <ChevronRightIcon size={13} />
          </button>

          <div className="pdf-toolbar-sep" />

          {/* Zoom In / Out / Fit Width */}
          <button
            type="button"
            onClick={handleZoomOut}
            className="pdf-page-btn"
            title="Zoom out (-15%)"
          >
            <ZoomOutIcon size={13} />
          </button>

          <button
            type="button"
            onClick={handleToggleFitWidth}
            className={`pdf-zoom-indicator ${isFitWidth ? "active" : ""}`}
            title={isFitWidth ? "Fit width (Click for 100%)" : `${zoomLevel}% (Click to fit width)`}
          >
            <FitWidthIcon size={12} />
            <span>{isFitWidth ? "Fit" : `${zoomLevel}%`}</span>
          </button>

          <button
            type="button"
            onClick={handleZoomIn}
            className="pdf-page-btn"
            title="Zoom in (+15%)"
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
              title={`Open Page ${currentPage} in new tab`}
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
              title="Close split-view viewer"
            >
              <CloseIcon size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 2. Grounded Evidence Banner */}
      {activeCitation && (
        <div className={`pdf-evidence-banner ${highlightPulse ? "highlight-flash" : ""}`}>
          <div className="pdf-evidence-header">
            <div className="pdf-evidence-title">
              <CheckShieldIcon size={13} color="#2563eb" />
              <span>{t.sourceViewer.citationFound}: <strong>{t.sourceViewer.page} {activeCitation.page}</strong></span>
            </div>
            <div className="pdf-evidence-actions">
              <button onClick={handleCopy} className="pdf-copy-excerpt-btn">
                {copied ? (
                  <>
                    <CheckIcon size={11} color="#10b981" />
                    <span>{t.common.copied}</span>
                  </>
                ) : (
                  <>
                    <CopyIcon size={11} />
                    <span>{t.sourceViewer.copySnippet}</span>
                  </>
                )}
              </button>
              <button
                onClick={onClearCitation}
                className="pdf-clear-cite-btn"
                title="Clear citation highlight"
              >
                <CloseIcon size={11} />
              </button>
            </div>
          </div>
          {/* Render Markdown table */}
          <div className="pdf-evidence-rendered-wrapper scrollbar-slim">
            <MarkdownRenderer content={activeCitation.snippet} />
          </div>
        </div>
      )}

      {/* 3. Original PDF Page Viewport */}
      <div className="pdf-display-viewport">
        {pdfUrl ? (
          <iframe
            key={`${currentDoc.document_id}-p${currentPage}`} // the page number stays in the key: Chrome's PDF viewer ignores a changed #page on a frame already open
            src={pdfUrl}
            title={`Financial Report: ${currentDoc.file_name}`}
            className="pdf-render-frame"
          />
        ) : (
          <div className="pdf-viewer-empty-state">
            <p className="pdf-empty-sub" role="status">{pdfFailed ? t.sourceViewer.pdfFailed : t.sourceViewer.pdfLoading}</p>
          </div>
        )}
      </div>
    </div>
  );
};
