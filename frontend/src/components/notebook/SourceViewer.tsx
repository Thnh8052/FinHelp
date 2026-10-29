import React, { useState } from "react";
import { CitationItem } from "../../types/chat";
import { FileTextIcon, CloseIcon, CheckIcon, CheckShieldIcon, CopyIcon } from "../common/Icons";
import "./notebook.css";

interface SourceViewerProps {
  activeCitation: CitationItem | null;
  onClearCitation: () => void;
  documentName?: string;
}

/**
 * Bảng đối chiếu nguồn trích dẫn (Evidence Grounding Inspector)
 * Đặt ở Panel bên phải (NotebookLM style)
 * Giúp người dùng/kế kiểm kiểm chứng trực tiếp từng con số về đúng trang và đoạn văn bản gốc trong BCTC.
 */
export const SourceViewer: React.FC<SourceViewerProps> = ({
  activeCitation,
  onClearCitation,
  documentName,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!activeCitation?.snippet) return;
    navigator.clipboard.writeText(activeCitation.snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="source-viewer">
      {/* Header Panel */}
      <div className="source-viewer-header">
        <div className="source-viewer-title-box">
          <CheckShieldIcon size={15} color="var(--accent-primary)" />
          <span className="source-viewer-title">
            Đối chiếu nguồn trích dẫn
          </span>
          <span className="source-viewer-badge">
            Evidence
          </span>
        </div>

        <button
          onClick={onClearCitation}
          title="Đóng bảng đối chiếu"
          className="source-close-btn"
        >
          <CloseIcon size={14} />
        </button>
      </div>

      {/* Nội dung đối chiếu */}
      <div className="source-body">
        {activeCitation ? (
          <div className="source-active-card">
            {/* Metadata: Trang & Bảng/Mục */}
            <div className="source-meta-bar">
              <span className="source-page-tag">
                Trang {activeCitation.page}
              </span>
              {activeCitation.row_label && (
                <span className="source-row-title">
                  {activeCitation.row_label}
                </span>
              )}
            </div>

            {documentName && (
              <div className="source-doc-ref">
                <FileTextIcon size={12} color="var(--text-dim)" />
                <span>{documentName}</span>
              </div>
            )}

            {/* Đoạn trích dẫn văn bản / Bảng số liệu */}
            <div className="source-excerpt-content">
              {activeCitation.snippet}
            </div>

            {/* Nút Sao chép đoạn trích */}
            <button onClick={handleCopy} className="source-copy-btn">
              {copied ? (
                <>
                  <CheckIcon size={13} color="#10b981" />
                  <span className="source-copied-text">Đã sao chép vào bộ nhớ tạm</span>
                </>
              ) : (
                <>
                  <CopyIcon size={13} />
                  <span>Sao chép đoạn trích dẫn</span>
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="source-empty-state">
            <div className="source-empty-icon">
              <FileTextIcon size={20} />
            </div>
            <div className="source-empty-title">
              Chưa chọn trích dẫn
            </div>
            <p className="source-empty-desc">
              Bấm vào các số trích dẫn <strong>[1]</strong>, <strong>[2]</strong> trong câu trả lời của FinAnalyst để xem văn bản gốc và đối chiếu số liệu từ Báo cáo tài chính.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
