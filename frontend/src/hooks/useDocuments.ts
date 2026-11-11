import { useEffect, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { ApiError, errorText, signInHelps } from "../services/api";
import { documentService } from "../services/documents";
import { DocumentRecord, isDocFailed, isDocProcessing } from "../types/notebook";
import { ShowToast } from "./useToast";

/**
 * Danh sách tài liệu của notebook: nguồn đang xem, nguồn đã chọn (kiểu NotebookLM: câu hỏi chỉ được trả lời trên các tài liệu này,
 * hệ thống không tự đoán phạm vi), tải lên (khách 1 tài liệu, người dùng 5) và theo dõi tiến độ xử lý.
 */
export function useDocuments(notebookId: string, maxSources: number, maxFileSizeMb: number, showToast: ShowToast, onLoginRequired: () => void) {
  const { t } = useLanguage();
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
      const usable = docs.find((d) => d.status === "ready");
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
      setDocuments(await documentService.list(notebookId));  // keeps the selection
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
        let anyReady = false;
        for (const id of watching) {
          const d = docs.find((x) => x.document_id === id);
          if (d?.status === "ready") {
            setSelectedDocIds((prev) => (prev.includes(id) ? prev : [...prev, id].slice(-maxSources)));  // also after a reload during processing
            anyReady = true;
          } else if (isDocFailed(d)) {
            setSelectedDocIds((prev) => prev.filter((x) => x !== id));  // Remove failed docs from active selection
            showToast(t.toasts.processFailed, "error");
          }
        }
        // Mỗi file đã có trạng thái riêng trong danh sách; chat chỉ mở khi mọi file xong nên chỉ báo một lần lúc đó
        if (anyReady && !docs.some(isDocProcessing)) showToast(t.toasts.allReady, "success");
      } catch {
        /* Network retry */
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [processingKey, notebookId, showToast, maxSources]);

  // Trong lúc đang gửi tệp lên, F5 hoặc đóng tab sẽ làm mất tệp: nhờ trình duyệt cảnh báo trước
  useEffect(() => {
    if (!isUploading) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isUploading]);

  /** Batch upload */
  const uploadFiles = async (files: File[]) => {
    if (files.length === 0 || isUploading) return;

    // 1. Deduplicate files within the selected batch
    const uniqueFiles: File[] = [];
    const seenInBatch = new Set<string>();
    for (const f of files) {
      const lower = f.name.toLowerCase();
      if (!seenInBatch.has(lower)) {
        seenInBatch.add(lower);
        uniqueFiles.push(f);
      }
    }

    // 2. Filter out files already in documents list (unless failed)
    const existingActiveNames = new Set(
      documents.filter((d) => !isDocFailed(d)).map((d) => d.file_name.toLowerCase())
    );

    const filesToUpload: File[] = [];
    for (const f of uniqueFiles) {
      if (existingActiveNames.has(f.name.toLowerCase())) {
        showToast(t.toasts.duplicateSkipped.replace("{name}", f.name), "warning");
      } else if (f.size > maxFileSizeMb * 1024 * 1024) {
        showToast(t.toasts.tooLarge.replace("{name}", f.name).replace("{mb}", String(maxFileSizeMb)), "warning");
      } else {
        filesToUpload.push(f);
      }
    }

    if (filesToUpload.length === 0) return;
    filesToUpload.sort((a, b) => a.size - b.size);  // tải lần lượt nên file nhẹ vào hàng trước và xong trước

    setIsUploading(true);
    let successCount = 0;
    try {
      for (const file of filesToUpload) {
        try {
          const data = await documentService.upload(notebookId, file);
          const newDoc: DocumentRecord = {
            document_id: data.document_id,
            notebook_id: notebookId,
            file_name: file.name,
            file_size_bytes: file.size,
            page_count: 0,
            status: "pending",
            created_at: new Date().toISOString(),
          };
          setDocuments((prev) => [newDoc, ...prev]);
          successCount++;
        } catch (fileErr) {
          if (fileErr instanceof ApiError) {
            const detail = errorText(fileErr, t, t.toasts.uploadFailed.replace("{name}", file.name));
            // Signing in helps only on 401 or for a guest's limit; a signed-in account at its limit gets a plain warning
            if (signInHelps(fileErr)) {
              showToast(detail, "warning", t.toasts.signInNow, onLoginRequired);
              break;
            } else if (fileErr.status === 403) {  // the notebook is full: the next files would be refused the same way
              showToast(detail, "warning");
              break;
            } else if (fileErr.status === 409) {
              showToast(detail, "warning");
            } else {
              showToast(detail, "error");
            }
          }
        }
      }
      if (successCount > 0) {
        showToast(t.toasts.uploaded.replace("{n}", String(successCount)), "success");
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
      showToast(t.toasts.docDeleted, "success");
      return true;
    } catch (err) {
      const message = err instanceof ApiError ? errorText(err, t, t.toasts.docDeleteFailed) : t.toasts.docDeleteConnection;
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
      showToast(t.toasts.docErrorsNoQuery, "warning");
    } else if (selectedDocIds.length >= maxSources) {
      showToast(t.toasts.maxActive.replace("{n}", String(maxSources)), "warning");
    } else {
      setSelectedDocIds([...selectedDocIds, docId]);
    }
  };

  const toggleAll = (selectAll: boolean) => {
    if (selectAll) {
      const usableIds = documents.filter((d) => d.status === "ready").map((d) => d.document_id);
      setSelectedDocIds(usableIds.slice(-maxSources));
    } else {
      setSelectedDocIds([]);
    }
  };

  const openable = documents.filter((d) => d.status === "ready");
  const activeDoc = openable.find((d) => d.document_id === activeDocId) || openable[0] || null;

  return {
    documents, activeDocId, setActiveDocId, activeDoc, selectedDocIds, isUploading, isDeleting,
    load, reset, reload, uploadFiles, remove, toggleSelected, toggleAll,
  };
}
