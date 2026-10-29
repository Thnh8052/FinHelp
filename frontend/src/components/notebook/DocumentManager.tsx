import React from "react";
import { DocumentRecord } from "../../types/notebook";
import { FileTextIcon, UploadCloudIcon } from "../common/Icons";
import "./notebook.css";

interface DocumentManagerProps {
  documents: DocumentRecord[];
  activeDocId: string | null;
  onSelectDoc: (docId: string) => void;
  onUpload: (file: File) => void;
  isUploading: boolean;
}

export const DocumentManager: React.FC<DocumentManagerProps> = ({
  documents,
  activeDocId,
  onSelectDoc,
  onUpload,
  isUploading,
}) => {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      onUpload(e.target.files[0]);
    }
  };

  return (
    <div className="doc-manager">
      {/* Header (NotebookLM Style: Nguồn) */}
      <div className="doc-manager-header">
        <h2 className="doc-manager-title">
          Nguồn tài liệu ({documents.length})
        </h2>

        <label className={`doc-upload-label ${isUploading ? "disabled" : ""}`}>
          <UploadCloudIcon size={12} />
          <span>{isUploading ? "Đang tải..." : "Thêm nguồn"}</span>
          <input
            type="file"
            accept=".pdf"
            disabled={isUploading}
            onChange={handleFileChange}
            className="doc-upload-input"
          />
        </label>
      </div>

      {/* Sources List (NotebookLM Style) */}
      <div className="doc-list">
        {documents.length === 0 ? (
          <div className="doc-empty">
            Chưa có tài liệu trong sổ tay. Bấm "Thêm nguồn" để tải lên báo cáo tài chính (PDF SEC 10-K / 10-Q).
          </div>
        ) : (
          documents.map((doc) => {
            const isActive = doc.document_id === activeDocId;

            return (
              <div
                key={doc.document_id}
                onClick={() => onSelectDoc(doc.document_id)}
                className={`doc-item ${isActive ? "active" : ""}`}
              >
                <FileTextIcon size={14} color={isActive ? "var(--accent-primary)" : "var(--text-dim)"} />
                <div className="doc-item-info">
                  <span
                    className="doc-item-name"
                    title={doc.file_name}
                  >
                    {doc.file_name}
                  </span>
                  <span className="doc-item-meta">
                    {doc.page_count ? `${doc.page_count} trang • ` : ""}SEC Filing
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
