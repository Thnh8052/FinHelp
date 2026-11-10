import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../services/api";
import { emptyOrNewNotebook, notebookService } from "../../services/notebooks";
import { useToast } from "../../hooks/useToast";
import { Notebook } from "../../types/notebook";

const REFRESH_WHILE_PROCESSING_MS = 5000;

/** Danh sách sổ tay của trang Hub: tải, đổi tên, xóa; tự cập nhật khi còn sổ tay đang xử lý tài liệu. */
export function useNotebookHub() {
  const { toast, showToast, closeToast } = useToast();
  const [notebooks, setNotebooks] = useState<Notebook[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setNotebooks(await notebookService.list());
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const isProcessing = !!notebooks?.some((n) => n.processing_count);
  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(() => void load(), REFRESH_WHILE_PROCESSING_MS);
    return () => clearInterval(timer);
  }, [isProcessing, load]);

  const explain = (err: unknown, fallback: string) => showToast(err instanceof ApiError ? err.detail || fallback : fallback, "error");

  const rename = async (notebookId: string, title: string, failedMessage: string): Promise<boolean> => {
    try {
      await notebookService.rename(notebookId, title);
      setNotebooks((prev) => prev?.map((n) => (n.notebook_id === notebookId ? { ...n, title } : n)) ?? prev);
      return true;
    } catch (err) {
      explain(err, failedMessage);
      return false;
    }
  };

  const remove = async (notebookId: string, doneMessage: string, failedMessage: string): Promise<void> => {
    try {
      await notebookService.remove(notebookId);
      setNotebooks((prev) => prev?.filter((n) => n.notebook_id !== notebookId) ?? prev);
      showToast(doneMessage, "info");
    } catch (err) {
      explain(err, failedMessage);
      void load();  // e.g. a file started processing in another tab
    }
  };

  const create = async (failedMessage: string): Promise<string | null> => {
    try {
      return (await emptyOrNewNotebook()).notebook_id;
    } catch (err) {
      explain(err, failedMessage);
      return null;
    }
  };

  return { notebooks, loadFailed, load, rename, remove, create, toast, closeToast };
}
