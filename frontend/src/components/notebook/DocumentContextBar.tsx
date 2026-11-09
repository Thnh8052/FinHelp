import React, { useState, useRef, useEffect } from "react";
import { DocumentRecord, isDocProcessing } from "../../types/notebook";
import { FileTextIcon, UploadCloudIcon, CheckShieldIcon, TrashIcon } from "../common/Icons";
import "./notebook.css";

interface DocumentContextBarProps {
  document: DocumentRecord | null;
  documents?: DocumentRecord[];
  onSelectDoc?: (docId: string) => void;
  /** Nguồn đã chọn (kiểu NotebookLM): câu hỏi chỉ được trả lời trên các tài liệu này. */
  selectedIds?: string[];
  onToggleDoc?: (docId: string) => void;
  /** Mở mẫu xác nhận / sửa thông tin (catalog) của một tài liệu. */
  onEditCatalog?: (docId: string) => void;
  onUpload: (file: File) => void;
  onDeleteDocument: (docId: string) => Promise<boolean>;
  isUploading: boolean;
  isDeleting: boolean;
  isAnalyzing?: boolean;
  isEvidenceOpen: boolean;
  onToggleEvidence: () => void;
  hasActiveCitation: boolean;
}

/**
 * Thanh hiển thị thông tin báo cáo tài chính đang phân tích
 * Cung cấp nút upload BCTC mới, bộ chọn tài liệu nếu có nhiều file,
 * và thanh hiển thị trạng thái hoạt động trực tiếp của hệ thống.
 */
export const DocumentContextBar: React.FC<DocumentContextBarProps> = ({
  document,
  documents = [],
  onSelectDoc,
  selectedIds = [],
  onToggleDoc,
  onEditCatalog,
  onUpload,
  onDeleteDocument,
  isUploading,
  isDeleting,
  isAnalyzing = false,
  isEvidenceOpen,
  onToggleEvidence,
  hasActiveCitation,
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentRecord | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const cancelDeleteRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    if (dropdownOpen) {
      window.document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      window.document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [dropdownOpen]);

  useEffect(() => {
    if (!deleteTarget) return;
    cancelDeleteRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isDeleting) setDeleteTarget(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [deleteTarget, isDeleting]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
    // Selecting the same PDF again must still emit a change event after a delete.
    e.target.value = "";
  };

  const confirmDelete = async () => {
    if (deleteTarget && await onDeleteDocument(deleteTarget.document_id)) {
      setDeleteTarget(null);
      setDropdownOpen(false);
    }
  };

  const multiSelect = !!onToggleDoc;
  const canOpenSourceList = documents.length > 0 && (!!onSelectDoc || multiSelect);
  const buttonLabel = multiSelect
    ? selectedIds.length === 0
      ? "Select source filings"
      : selectedIds.length === 1
      ? documents.find((d) => d.document_id === selectedIds[0])?.file_name ?? "1 filing selected"
      : `${selectedIds.length} filings selected`
    : document
    ? document.file_name
    : "No filing selected";

  return (
    <div className="doc-context-bar">
      {/* Document info */}
      <div className="doc-context-info">
        <div className="doc-context-icon">
          <FileTextIcon size={16} color="var(--accent-primary)" />
        </div>

        <div className="doc-context-details">
          <div className="doc-context-title-row">
            {canOpenSourceList ? (
              <div ref={dropdownRef} className="doc-selector-dropdown">
                <button
                  type="button"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="doc-selector-btn"
                  title="Open sources list"
                  aria-expanded={dropdownOpen}
                  aria-haspopup="dialog"
                >
                  <span className="doc-context-name">{buttonLabel}</span>
                  <span className="doc-selector-arrow">▾</span>
                </button>

                {dropdownOpen && (
                  <div className="doc-selector-menu" role="dialog" aria-label="Sources list">
                    {documents.map((d) => {
                      const checked = multiSelect
                        ? selectedIds.includes(d.document_id)
                        : d.document_id === document?.document_id;
                      return (
                        <div
                          key={d.document_id}
                          className={`doc-selector-item ${checked ? "active" : ""}`}
                        >
                          {multiSelect && (
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => onToggleDoc!(d.document_id)}
                              aria-label={`Use ${d.file_name} for queries`}
                            />
                          )}
                          <button
                            type="button"
                            className="doc-selector-source"
                            onClick={() => {
                              onSelectDoc?.(d.document_id);
                              if (!multiSelect) setDropdownOpen(false);
                            }}
                            title={d.file_name}
                          >
                            <FileTextIcon size={13} />
                            <span className="doc-item-name">{d.file_name}</span>
                          </button>
                          {onEditCatalog && d.status === "ready" && (
                            <button
                              type="button"
                              className="doc-item-edit"
                              onClick={() => {
                                onEditCatalog(d.document_id);
                              }}
                            >
                              Details
                            </button>
                          )}
                          <button
                            type="button"
                            className="doc-item-delete"
                            onClick={() => {
                              setDeleteTarget(d);
                              setDropdownOpen(false);
                            }}
                            aria-label={`Delete ${d.file_name}`}
                            title={`Delete ${d.file_name}`}
                            disabled={isDeleting}
                          >
                            <TrashIcon size={14} />
                            <span>Delete</span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <span
                className="doc-context-name"
                title={document?.file_name || "No filing selected"}
              >
                {document ? document.file_name : "No financial report uploaded"}
              </span>
            )}

          </div>

          <div className="doc-context-sub">
            {isUploading ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Processing and extracting filing data...</span>
              </>
            ) : isAnalyzing ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Verifying metrics &amp; calculating ratios...</span>
              </>
            ) : isDocProcessing(document) ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Processing document layout and tables...</span>
              </>
            ) : document?.status === "failed" ? (
              <>
                <span className="doc-status-dot idle" />
                <span>Failed to process document • Please try uploading again</span>
              </>
            ) : document ? (
              <>
                <span className="doc-status-dot" />
                <span>
                  {document.page_count ? `${document.page_count} pages • ` : ""}
                  System active • Ready for analysis
                </span>
              </>
            ) : (
              <>
                <span className="doc-status-dot idle" />
                <span>No filings loaded • Upload a PDF report to begin</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Action buttons */}
      <div className="doc-context-actions">
        {/* Upload Button */}
        <label className={`doc-upload-btn ${isUploading ? "disabled" : ""}`}>
          <UploadCloudIcon size={13} />
          <span>{isUploading ? "Processing PDF..." : document ? "Add PDF" : "Upload PDF"}</span>
          <input
            type="file"
            accept=".pdf"
            disabled={isUploading}
            onChange={handleFileChange}
            className="doc-upload-input"
          />
        </label>

        {/* Evidence Toggle */}
        <button
          onClick={onToggleEvidence}
          title={isEvidenceOpen ? "Hide citations drawer" : "Open citations drawer"}
          className={`doc-evidence-toggle-btn ${isEvidenceOpen ? "active" : ""}`}
        >
          <CheckShieldIcon size={13} color={isEvidenceOpen ? "var(--accent-primary)" : "currentColor"} />
          <span>Verified Citations {hasActiveCitation ? "•" : ""}</span>
        </button>
      </div>

      {deleteTarget && (
        <div className="doc-delete-confirm" role="alertdialog" aria-modal="true" aria-labelledby="doc-delete-title" aria-describedby="doc-delete-description">
          <p id="doc-delete-title" className="doc-delete-confirm-title">Delete document?</p>
          <p id="doc-delete-description" className="doc-delete-confirm-description">
            “{deleteTarget.file_name}” and its indexed data will be permanently removed.
          </p>
          <div className="doc-delete-confirm-actions">
            <button ref={cancelDeleteRef} type="button" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Cancel
            </button>
            <button type="button" className="doc-delete-confirm-button" onClick={confirmDelete} disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete document"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
