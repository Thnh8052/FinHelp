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
            showToast("Tài liệu đã sẵn sàng. Bạn có thể bắt đầu đặt câu hỏi.", "success");
          } else if (isDocFailed(d)) {
            setSelectedDocIds((prev) => prev.filter((x) => x !== id));  // tài liệu lỗi không trả lời được: bỏ khỏi danh sách nguồn đã chọn
            showToast("Không xử lý được tài liệu này. Vui lòng thử tải lên lại.", "error");
          }
        }
      } catch {
        /* mạng chập chờn: thử lại ở lần sau */
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
      // Tệp mới luôn được chọn; đã đủ hạn mức thì thay nguồn chọn sớm nhất (khách chỉ có 1 nguồn: chính tệp mới)
      setSelectedDocIds((prev) => [...prev.filter((x) => x !== newDoc.document_id), newDoc.document_id].slice(-maxSources));
      showToast("Tải tệp thành công! Đang tiến hành trích xuất dữ liệu BCTC.", "success");
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail || "Tải lên tài liệu thất bại.";
        // Chạm trần hạn mức của khách: thông báo kèm nút đăng nhập
        if (err.status === 403 || detail.toLowerCase().includes("đăng nhập")) {
          showToast(detail, "warning", "Đăng nhập ngay", onLoginRequired);
        } else {
          showToast(detail, "error");
        }
      } else {
        showToast("Không thể kết nối đến máy chủ khi tải lên tài liệu.", "error");
      }
    } finally {
      setIsUploading(false);
    }
  };

  /** Tải lên nhiều tệp cùng lúc (Batch Upload từ Dropzone) */
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
            const detail = fileErr.detail || `Tải lên ${file.name} thất bại.`;
            if (fileErr.status === 403 || detail.toLowerCase().includes("đăng nhập")) {
              showToast(detail, "warning", "Đăng nhập ngay", onLoginRequired);
              break;
            } else {
              showToast(detail, "error");
            }
          }
        }
      }
      if (successCount > 0) {
        showToast(`Đã tải lên ${successCount} tệp BCTC! Đang tiến hành trích xuất dữ liệu.`, "success");
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
      showToast("Đã xóa tài liệu. Bạn có thể tải lên nguồn khác.", "success");
      return true;
    } catch (err) {
      const message = err instanceof ApiError ? err.detail || "Không thể xóa tài liệu." : "Không thể kết nối đến máy chủ khi xóa tài liệu.";
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
      showToast("Tài liệu này xử lý lỗi nên không dùng làm nguồn được. Vui lòng tải lên lại.", "warning");
    } else if (selectedDocIds.length >= maxSources) {
      showToast(`Chỉ chọn được tối đa ${maxSources} tài liệu nguồn cho một câu hỏi.`, "warning");
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
