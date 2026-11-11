import React, { useState, useRef } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { processingErrorText } from "../../services/api";
import { DocumentRecord, isDocProcessing, isDocFailed } from "../../types/notebook";
import {
  FileTextIcon,
  UploadCloudIcon,
  CloseIcon,
  TrashIcon,
  InfoCircleIcon,
  CheckIcon,
} from "../common/Icons";
import "./notebook.css";

interface DocumentManagerProps {
  documents: DocumentRecord[];
  activeDocId: string | null;
  selectedDocIds: string[];
  onSelectDoc: (docId: string) => void;
  onToggleDoc: (docId: string) => void;
  onToggleAllDocs?: (selectAll: boolean) => void;
  onOpenDocPdf?: (doc: DocumentRecord) => void;
  onUploadFiles: (files: File[]) => void;
  onDeleteDocument: (docId: string) => Promise<boolean> | void;
  onEditCatalog?: (docId: string) => void;
  onClose?: () => void;
  isUploading: boolean;
  isDeleting: boolean;
  maxSources: number;
  maxFileSizeMb: number;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({
  documents,
  activeDocId,
  selectedDocIds,
  onSelectDoc: _onSelectDoc,
  onToggleDoc,
  onToggleAllDocs,
  onOpenDocPdf,
  onUploadFiles,
  onDeleteDocument,
  onEditCatalog,
  onClose,
  isUploading,
  isDeleting,
  maxSources,
  maxFileSizeMb,
}) => {
  const { t } = useLanguage();
  const [isDragging, setIsDragging] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Đang gửi tệp hoặc còn tài liệu đang xử lý: chưa nhận thêm tệp
  const isBusy = isUploading || documents.some(isDocProcessing);
  const selectableCount = documents.filter((d) => d.status === "ready").length;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isBusy) return;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const pdfFiles = Array.from(e.dataTransfer.files).filter((f) =>
        f.name.toLowerCase().endsWith(".pdf")
      );
      if (pdfFiles.length > 0) {
        onUploadFiles(pdfFiles);
      }
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (isBusy) return;
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      e.target.value = "";
      onUploadFiles(files);
    }
  };

  const allSelected =
    selectableCount > 0 && selectedDocIds.length === selectableCount;

  const handleMasterCheckbox = () => {
    if (onToggleAllDocs) {
      onToggleAllDocs(!allSelected);
    } else {
      // Fallback toggle từng file nếu không có onToggleAllDocs
      documents.forEach((d) => {
        if (allSelected) {
          if (selectedDocIds.includes(d.document_id)) onToggleDoc(d.document_id);
        } else {
          if (!selectedDocIds.includes(d.document_id)) onToggleDoc(d.document_id);
        }
      });
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "0 MB";
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="doc-drawer-container">
      {/* 1. Header Panel */}
      <div className="doc-drawer-header">
        <div className="doc-drawer-title-box">
          <FileTextIcon size={15} color="var(--accent-primary, #2563eb)" />
          <span className="doc-drawer-title">{t.sourcesDrawer.title}</span>
          <span className="doc-drawer-badge">{documents.length} {t.sourcesDrawer.filesCount}</span>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="doc-drawer-close-btn"
            title={t.sourcesDrawer.closeDrawer}
          >
            <CloseIcon size={13} />
          </button>
        )}
      </div>

      {/* 2. Drag & Dropzone */}
      <div className="doc-drawer-dropzone-wrap">
        <div
          className={`doc-drawer-dropzone ${isDragging ? "dragging" : ""} ${
            isBusy ? "uploading" : ""
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={(e) => {
            if (e.target === fileInputRef.current) return;
            if (!isBusy) fileInputRef.current?.click();
          }}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            disabled={isBusy}
            onChange={handleFileInputChange}
            className="hidden-file-input"
          />

          <div className="doc-dropzone-icon">
            <UploadCloudIcon size={18} color="var(--accent-primary, #2563eb)" />
          </div>
          <p className="doc-dropzone-text">
            {isBusy ? t.workspace.placeholderProcessing : t.sourcesDrawer.dropzoneIdle}
          </p>
          <p className="doc-dropzone-subtext">
            {t.sourcesDrawer.dropzoneSubtext.replace("{docs}", String(maxSources)).replace("{mb}", String(maxFileSizeMb))}
          </p>
        </div>
      </div>

      {/* 3. Controls & Select All */}
      <div className="doc-drawer-controls">
        <label className="doc-master-checkbox-label">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleMasterCheckbox}
            disabled={isBusy || selectableCount === 0}
            className="doc-checkbox"
          />
          <span>{t.sourcesDrawer.selectAll}</span>
        </label>
        <span className="doc-active-counter">
          {selectedDocIds.length}/{selectableCount} {t.sourcesDrawer.activeCounter}
        </span>
      </div>

      {/* 4. Document Cards List */}
      <div className="doc-drawer-list scrollbar-slim">
        {documents.length === 0 ? (
          <div className="doc-drawer-empty">
            <p>{t.sourcesDrawer.noReportsYet}</p>
            <p className="sub">{t.sourcesDrawer.dragAndDropPrompt}</p>
          </div>
        ) : (
          documents.map((doc) => {
            const isSelected = selectedDocIds.includes(doc.document_id);
            const isProcessing = isDocProcessing(doc);
            const isFailed = isDocFailed(doc);
            const isActive = doc.document_id === activeDocId;

            return (
              <div
                key={doc.document_id}
                className={`doc-card-item ${isActive ? "active" : ""} ${
                  isSelected ? "selected" : ""
                }`}
              >
                <div className="doc-card-body">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    disabled={isProcessing || isFailed}
                    onChange={() => onToggleDoc(doc.document_id)}
                    className="doc-checkbox"
                    title={isSelected ? t.sourcesDrawer.excludeFromAnalysis : t.sourcesDrawer.includeInAnalysis}
                  />

                  <div className="doc-card-details">
                    <div className="doc-card-top-row">
                      <span className="doc-card-name" title={doc.file_name}>
                        {doc.file_name}
                      </span>
                      <span className="doc-card-tag">
                        {doc.status === "pending"
                          ? t.sourcesDrawer.queued
                          : isProcessing
                          ? t.sourcesDrawer.processingDots
                          : isFailed
                          ? t.sourcesDrawer.failedBadge
                          : t.sourcesDrawer.auditedFiling}
                      </span>
                    </div>

                    <div className="doc-card-meta">
                      {doc.page_count ? <span>{t.sourcesDrawer.pagesCount.replace("{n}", String(doc.page_count))}</span> : null}
                      {doc.page_count ? <span>•</span> : null}
                      <span>{formatFileSize(doc.file_size_bytes)}</span>
                      {doc.status === "ready" && (
                        <>
                          <span>•</span>
                          <span className="doc-status-ok">{t.sourcesDrawer.statusReady}</span>
                        </>
                      )}
                    </div>

                    {isFailed && doc.error_message && <p className="doc-card-error">{processingErrorText(doc.error_message, t)}</p>}
                    {doc.tables_may_be_inaccurate && (
                      <p className="doc-card-error">
                        {t.sourcesDrawer.tablesWarning}
                      </p>
                    )}

                    {/* Action Bar: nothing while the file is being processed; a failed file can only be deleted */}
                    {!isProcessing && <div className="doc-card-actions">
                      {!isFailed && onOpenDocPdf && (
                        <button
                          type="button"
                          onClick={() => onOpenDocPdf(doc)}
                          className="doc-btn-open-pdf"
                          title={t.sourcesDrawer.openInReader}
                        >
                          <FileTextIcon size={12} color="#60a5fa" />
                          <span>{t.sourcesDrawer.viewPdf}</span>
                        </button>
                      )}

                      <div className="doc-card-subactions">
                        {!isFailed && onEditCatalog && (
                          <button
                            type="button"
                            onClick={() => onEditCatalog(doc.document_id)}
                            className="doc-subaction-btn"
                            title={t.sourcesDrawer.viewMetadata}
                          >
                            <InfoCircleIcon size={12} />
                            <span>{t.sourcesDrawer.details}</span>
                          </button>
                        )}

                        {!isFailed && <span className="doc-subaction-sep">|</span>}

                        {deleteTargetId === doc.document_id ? (
                          <div className="doc-delete-confirm-box">
                            <span className="doc-delete-text">{t.sourcesDrawer.deletePrompt}</span>
                            <button
                              type="button"
                              onClick={() => {
                                onDeleteDocument(doc.document_id);
                                setDeleteTargetId(null);
                              }}
                              disabled={isDeleting}
                              className="doc-confirm-yes"
                              title={t.sourcesDrawer.confirmDelete}
                            >
                              <CheckIcon size={12} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTargetId(null)}
                              className="doc-confirm-no"
                              title={t.common.cancel}
                            >
                              <CloseIcon size={12} />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setDeleteTargetId(doc.document_id)}
                            className="doc-subaction-btn delete"
                            title={t.sourcesDrawer.deleteFromSession}
                          >
                            <TrashIcon size={12} />
                            <span>{t.common.delete}</span>
                          </button>
                        )}
                      </div>
                    </div>}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 5. Footer Panel */}
      <div className="doc-drawer-footer">
        <span>{t.sourcesDrawer.securityNote}</span>
      </div>
    </div>
  );
};
