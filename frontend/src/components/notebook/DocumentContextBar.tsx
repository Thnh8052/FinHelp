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
      ? "Chọn tài liệu nguồn"
      : selectedIds.length === 1
      ? documents.find((d) => d.document_id === selectedIds[0])?.file_name ?? "1 nguồn đã chọn"
      : `${selectedIds.length} nguồn đã chọn`
    : document
    ? document.file_name
    : "Chưa chọn tài liệu";

  return (
    <div className="doc-context-bar">
      {/* Thông tin tài liệu BCTC */}
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
                  title="Mở danh sách nguồn tài liệu"
                  aria-expanded={dropdownOpen}
                  aria-haspopup="dialog"
                >
                  <span className="doc-context-name">{buttonLabel}</span>
                  <span className="doc-selector-arrow">▾</span>
                </button>

                {dropdownOpen && (
                  <div className="doc-selector-menu" role="dialog" aria-label="Danh sách nguồn tài liệu">
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
                              aria-label={`Dùng ${d.file_name} làm nguồn cho câu hỏi`}
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
                          {onEditCatalog && d.indexing_status === "completed" && (
                            <button
                              type="button"
                              className="doc-item-edit"
                              onClick={() => {
                                onEditCatalog(d.document_id);
                              }}
                            >
                              Thông tin
                            </button>
                          )}
                          <button
                            type="button"
                            className="doc-item-delete"
                            onClick={() => {
                              setDeleteTarget(d);
                              setDropdownOpen(false);
                            }}
                            aria-label={`Xóa ${d.file_name}`}
                            title={`Xóa ${d.file_name}`}
                            disabled={isDeleting}
                          >
                            <TrashIcon size={14} />
                            <span>Xóa</span>
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
                title={document?.file_name || "Chưa chọn tài liệu"}
              >
                {document ? document.file_name : "Chưa tải lên Báo cáo tài chính"}
              </span>
            )}

          </div>

          <div className="doc-context-sub">
            {isUploading ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Đang xử lý & trích xuất dữ liệu BCTC...</span>
              </>
            ) : isAnalyzing ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Đang đối chiếu dữ liệu & tính toán chỉ số...</span>
              </>
            ) : isDocProcessing(document) ? (
              <>
                <span className="doc-status-dot processing" />
                <span>Đang xử lý tài liệu (bảng biểu, số liệu)... có thể mất vài phút</span>
              </>
            ) : document?.parsing_status === "failed" ? (
              <>
                <span className="doc-status-dot idle" />
                <span>Không xử lý được tài liệu • Vui lòng tải lên lại</span>
              </>
            ) : document ? (
              <>
                <span className="doc-status-dot" />
                <span>
                  {document.page_count ? `${document.page_count} trang • ` : ""}
                  Hệ thống hoạt động • Sẵn sàng phân tích
                </span>
              </>
            ) : (
              <>
                <span className="doc-status-dot idle" />
                <span>Chưa nạp tài liệu • Tải file PDF báo cáo tài chính để bắt đầu</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Hành động: Upload BCTC & Bật/Tắt bảng đối chiếu */}
      <div className="doc-context-actions">
        {/* Nút Upload / Đổi file */}
        <label className={`doc-upload-btn ${isUploading ? "disabled" : ""}`}>
          <UploadCloudIcon size={13} />
          <span>{isUploading ? "Đang xử lý PDF..." : document ? "Thêm PDF" : "Tải lên PDF"}</span>
          <input
            type="file"
            accept=".pdf"
            disabled={isUploading}
            onChange={handleFileChange}
            className="doc-upload-input"
          />
        </label>

        {/* Nút Bật / Tắt Bảng đối chiếu nguồn */}
        <button
          onClick={onToggleEvidence}
          title={isEvidenceOpen ? "Ẩn bảng đối chiếu nguồn" : "Mở bảng đối chiếu nguồn"}
          className={`doc-evidence-toggle-btn ${isEvidenceOpen ? "active" : ""}`}
        >
          <CheckShieldIcon size={13} color={isEvidenceOpen ? "var(--accent-primary)" : "currentColor"} />
          <span>Đối chiếu nguồn {hasActiveCitation ? "•" : ""}</span>
        </button>
      </div>

      {deleteTarget && (
        <div className="doc-delete-confirm" role="alertdialog" aria-modal="true" aria-labelledby="doc-delete-title" aria-describedby="doc-delete-description">
          <p id="doc-delete-title" className="doc-delete-confirm-title">Xóa tài liệu?</p>
          <p id="doc-delete-description" className="doc-delete-confirm-description">
            “{deleteTarget.file_name}” và dữ liệu phân tích liên quan sẽ bị xóa vĩnh viễn.
          </p>
          <div className="doc-delete-confirm-actions">
            <button ref={cancelDeleteRef} type="button" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Hủy
            </button>
            <button type="button" className="doc-delete-confirm-button" onClick={confirmDelete} disabled={isDeleting}>
              {isDeleting ? "Đang xóa..." : "Xóa tài liệu"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
