import { useEffect, useState } from "react";
import { ApiError } from "../services/api";
import { documentService } from "../services/documents";
import { DocumentRecord, isDocFailed, isDocProcessing } from "../types/notebook";
import { ShowToast } from "./useToast";

/**
 * Danh sách tài liệu của notebook: nguồn đang xem, nguồn đã chọn (kiểu NotebookLM: câu hỏi chỉ được trả lời trên các tài liệu này,
 * hệ thống không tự đoán phạm vi), tải lên (khách 1 tài liệu, người dùng 5) và theo dõi tiến độ xử lý.
 */
export function useDocuments(notebookId: string, maxSources: number, showToast: ShowToast, onLoginRequired: () => void) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [activeDocId, setActiveDocId] = useState<string | null>(null);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  /** Thay cả danh sách (lúc tải notebook): tài liệu đầu tiên được xem, tài liệu đầu tiên không lỗi được chọn. */
  const load = (docs: DocumentRecord[]) => {
    setDocuments(docs);
    if (docs.length > 0) {
      setActiveDocId(docs[0].document_id);
      const usable = docs.find((d) => !isDocFailed(d));
      setSelectedDocIds(usable ? [usable.document_id] : []);
    } else {
      setActiveDocId(null);
      setSelectedDocIds([]);
    }
  };

  const reset = () => {
    setDocuments([]);
    setActiveDocId(null);
    setSelectedDocIds([]);
  };

  const reload = async () => {
    try {
      setDocuments(await documentService.list(notebookId));
    } catch {
      /* giữ danh sách hiện có */
    }
  };

  // Theo dõi tiến độ xử lý tài liệu: hỏi lại danh sách mỗi 3 giây cho tới khi các tài liệu đang xử lý xong
  const processingKey = documents.filter(isDocProcessing).map((d) => d.document_id).join(",");
  useEffect(() => {
    if (!processingKey) return;
    const watching = processingKey.split(",");
    const timer = setInterval(async () => {
      try {
        const docs = await documentService.list(notebookId);
        setDocuments(docs);
        for (const id of watching) {
          const d = docs.find((x) => x.document_id === id);
          if (d?.indexing_status === "completed") {
            showToast("Document is ready. You can now ask questions.", "success");
          } else if (isDocFailed(d)) {
            setSelectedDocIds((prev) => prev.filter((x) => x !== id));  // Remove failed docs from active selection
            showToast("Failed to process document. Please try uploading again.", "error");
          }
        }
      } catch {
        /* Network retry */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [processingKey, notebookId, showToast]);

  const upload = async (file: File) => {
    setIsUploading(true);
    try {
      const data = await documentService.upload(notebookId, file);
      const newDoc: DocumentRecord = {
        document_id: data.document_id,
        notebook_id: notebookId,
        file_name: file.name,
        file_size_bytes: file.size,
        file_path: `storage/pdfs/${notebookId}/${data.document_id}.pdf`,
        page_count: 0,
        parsing_status: "processing",
        indexing_status: "pending",
        created_at: new Date().toISOString(),
      };
      setDocuments((prev) => [newDoc, ...prev]);
      setActiveDocId(newDoc.document_id);
      setSelectedDocIds((prev) => [...prev.filter((x) => x !== newDoc.document_id), newDoc.document_id].slice(-maxSources));
      showToast("Upload successful! Processing financial filing.", "success");
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail || "Document upload failed.";
        if (err.status === 403 || detail.toLowerCase().includes("login") || detail.toLowerCase().includes("sign in") || detail.toLowerCase().includes("đăng nhập")) {
          showToast(detail, "warning", "Sign in now", onLoginRequired);
        } else {
          showToast(detail, "error");
        }
      } else {
        showToast("Unable to connect to server during upload.", "error");
      }
    } finally {
      setIsUploading(false);
    }
  };

  /** Batch upload */
  const uploadFiles = async (files: File[]) => {
    if (files.length === 0) return;
    setIsUploading(true);
    let successCount = 0;
    try {
      for (const file of files) {
        try {
          const data = await documentService.upload(notebookId, file);
          const newDoc: DocumentRecord = {
            document_id: data.document_id,
            notebook_id: notebookId,
            file_name: file.name,
            file_size_bytes: file.size,
            file_path: `storage/pdfs/${notebookId}/${data.document_id}.pdf`,
            page_count: 0,
            parsing_status: "processing",
            indexing_status: "pending",
            created_at: new Date().toISOString(),
          };
          setDocuments((prev) => [newDoc, ...prev]);
          setActiveDocId(newDoc.document_id);
          setSelectedDocIds((prev) => [...prev.filter((x) => x !== newDoc.document_id), newDoc.document_id].slice(-maxSources));
          successCount++;
        } catch (fileErr) {
          if (fileErr instanceof ApiError) {
            const detail = fileErr.detail || `Upload of ${file.name} failed.`;
            if (fileErr.status === 403 || detail.toLowerCase().includes("login") || detail.toLowerCase().includes("sign in") || detail.toLowerCase().includes("đăng nhập")) {
              showToast(detail, "warning", "Sign in now", onLoginRequired);
              break;
            } else {
              showToast(detail, "error");
            }
          }
        }
      }
      if (successCount > 0) {
        showToast(`Uploaded ${successCount} report(s)! Extracting document layout.`, "success");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const remove = async (documentId: string): Promise<boolean> => {
    setIsDeleting(true);
    try {
      await documentService.remove(documentId);
      setDocuments((previous) => {
        const remaining = previous.filter((document) => document.document_id !== documentId);
        setActiveDocId((activeId) => activeId === documentId ? remaining[0]?.document_id ?? null : activeId);
        return remaining;
      });
      setSelectedDocIds((previous) => previous.filter((id) => id !== documentId));
      showToast("Document deleted successfully.", "success");
      return true;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail || "Unable to delete document." : "Unable to connect to server to delete document.";
      showToast(message, "error");
      return false;
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleSelected = (docId: string) => {
    if (selectedDocIds.includes(docId)) {
      setSelectedDocIds(selectedDocIds.filter((x) => x !== docId));
    } else if (isDocFailed(documents.find((d) => d.document_id === docId))) {
      showToast("This document encountered processing errors and cannot be queried. Please re-upload.", "warning");
    } else if (selectedDocIds.length >= maxSources) {
      showToast(`Maximum ${maxSources} filings can be active simultaneously.`, "warning");
    } else {
      setSelectedDocIds([...selectedDocIds, docId]);
    }
  };

  const toggleAll = (selectAll: boolean) => {
    if (selectAll) {
      const usableIds = documents.filter((d) => !isDocFailed(d)).map((d) => d.document_id);
      setSelectedDocIds(usableIds.slice(-maxSources));
    } else {
      setSelectedDocIds([]);
    }
  };

  const activeDoc = documents.find((d) => d.document_id === activeDocId) || documents[0] || null;

  return {
    documents, activeDocId, setActiveDocId, activeDoc, selectedDocIds, isUploading, isDeleting,
    load, reset, reload, upload, uploadFiles, remove, toggleSelected, toggleAll,
  };
}
