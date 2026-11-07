import React, { useState, useRef } from "react";
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
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      onUploadFiles(files);
      e.target.value = "";
    }
  };

  const allSelected =
    documents.length > 0 && selectedDocIds.length === documents.length;

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
          <span className="doc-drawer-title">Nguồn phiên này</span>
          <span className="doc-drawer-badge">{documents.length} File</span>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="doc-drawer-close-btn"
            title="Đóng danh sách nguồn"
          >
            <CloseIcon size={13} />
          </button>
        )}
      </div>

      {/* 2. Vùng Kéo Thả / Batch Upload (Dropzone) */}
      <div className="doc-drawer-dropzone-wrap">
        <div
          className={`doc-drawer-dropzone ${isDragging ? "dragging" : ""} ${
            isUploading ? "uploading" : ""
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            disabled={isUploading}
            onChange={handleFileInputChange}
            style={{ display: "none" }}
          />

          <div className="doc-dropzone-icon">
            <UploadCloudIcon size={18} color="var(--accent-primary, #2563eb)" />
          </div>
          <p className="doc-dropzone-text">
            {isUploading ? "Đang tải và trích xuất BCTC..." : "Kéo thả hoặc tải thêm BCTC"}
          </p>
          <p className="doc-dropzone-subtext">
            Chọn nhiều file PDF cùng lúc (Tối đa 5 file)
          </p>
        </div>
      </div>

      {/* 3. Bộ Đếm & Checkbox Bật Tất Cả Cho RAG */}
      <div className="doc-drawer-controls">
        <label className="doc-master-checkbox-label">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={handleMasterCheckbox}
            disabled={documents.length === 0}
            className="doc-checkbox"
          />
          <span>Bật tất cả cho RAG</span>
        </label>
        <span className="doc-active-counter">
          {selectedDocIds.length}/{documents.length} kích hoạt
        </span>
      </div>

      {/* 4. Danh Sách Chi Tiết Từng Tài Liệu BCTC */}
      <div className="doc-drawer-list scrollbar-slim">
        {documents.length === 0 ? (
          <div className="doc-drawer-empty">
            <p>Chưa có BCTC nào trong phiên này.</p>
            <p className="sub">Kéo thả file PDF vào ô phía trên để bắt đầu đối chiếu.</p>
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
                    title={isSelected ? "Bỏ chọn khỏi ngữ cảnh RAG" : "Bật làm ngữ cảnh trả lời RAG"}
                  />

                  <div className="doc-card-details">
                    <div className="doc-card-top-row">
                      <span className="doc-card-name" title={doc.file_name}>
                        {doc.file_name}
                      </span>
                      <span className="doc-card-tag">
                        {isProcessing
                          ? "Đang xử lý..."
                          : isFailed
                          ? "Lỗi"
                          : "10-K Kiểm toán"}
                      </span>
                    </div>

                    <div className="doc-card-meta">
                      {doc.page_count ? <span>{doc.page_count} trang</span> : null}
                      {doc.page_count ? <span>•</span> : null}
                      <span>{formatFileSize(doc.file_size_bytes)}</span>
                      {doc.indexing_status === "completed" && (
                        <>
                          <span>•</span>
                          <span className="doc-status-ok">Đã sẵn sàng</span>
                        </>
                      )}
                    </div>

                    {/* Action Bar dưới mỗi tệp */}
                    <div className="doc-card-actions">
                      {onOpenDocPdf && (
                        <button
                          type="button"
                          onClick={() => onOpenDocPdf(doc)}
                          className="doc-btn-open-pdf"
                          title="Mở tài liệu này trên trình đọc PDF Split-View"
                        >
                          <FileTextIcon size={12} color="#60a5fa" />
                          <span>Mở xem PDF</span>
                        </button>
                      )}

                      <div className="doc-card-subactions">
                        {onEditCatalog && (
                          <button
                            type="button"
                            onClick={() => onEditCatalog(doc.document_id)}
                            className="doc-subaction-btn"
                            title="Xem thông tin kiểm toán & kỳ báo cáo"
                          >
                            <InfoCircleIcon size={12} />
                            <span>Chi tiết</span>
                          </button>
                        )}

                        <span className="doc-subaction-sep">|</span>

                        {deleteTargetId === doc.document_id ? (
                          <div className="doc-delete-confirm-box">
                            <span className="doc-delete-text">Xóa?</span>
                            <button
                              type="button"
                              onClick={() => {
                                onDeleteDocument(doc.document_id);
                                setDeleteTargetId(null);
                              }}
                              disabled={isDeleting}
                              className="doc-confirm-yes"
                              title="Xác nhận xóa"
                            >
                              <CheckIcon size={12} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTargetId(null)}
                              className="doc-confirm-no"
                              title="Hủy"
                            >
                              <CloseIcon size={12} />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setDeleteTargetId(doc.document_id)}
                            className="doc-subaction-btn delete"
                            title="Xóa tài liệu khỏi phiên này"
                          >
                            <TrashIcon size={12} />
                            <span>Xóa</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 5. Footer Panel */}
      <div className="doc-drawer-footer">
        <span>🔒 Nguồn chỉ lưu trong phiên chat này, không bị ghi đè.</span>
      </div>
    </div>
  );
};
