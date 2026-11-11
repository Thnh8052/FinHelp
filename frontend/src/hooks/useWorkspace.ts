import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../services/api";
import { chatService } from "../services/chat";
import { documentService } from "../services/documents";
import { emptyOrNewNotebook, guestNotebook, notebookService } from "../services/notebooks";
import { Notebook, isDocProcessing } from "../types/notebook";
import { useChat } from "./useChat";
import { useDocuments } from "./useDocuments";
import { useToast } from "./useToast";

const REFRESH_WHILE_PROCESSING_MS = 5000;

/** Một bước tải có thể hỏng mà không chặn các bước sau (null khi hỏng). */
const attempt = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null);

/**
 * Không gian làm việc của một sổ tay (mỗi sổ tay là một đoạn chat).
 * Người dùng đăng nhập: sổ tay nằm trên URL (/app/:notebookId). Khách: một sổ tay riêng do backend cấp, mã lưu trong trình duyệt.
 */
export function useWorkspace(onLoginRequired: () => void) {
  const { isAuthenticated, isLoading: isAuthLoading, user, guestQuota } = useAuth();
  const { toast, showToast, closeToast } = useToast();
  const { notebookId: routeNotebookId } = useParams();
  const navigate = useNavigate();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [notebookId, setNotebookId] = useState("");
  const opening = useRef("");
  // Documents per notebook = sources per question; the backend's numbers (/auth/me, /auth/guest-quota), never a copy of them
  const maxSources = (isAuthenticated ? user?.quota.max_upload_documents : guestQuota?.max_upload_documents) ?? 1;

  const notebookTitle = notebooks.find((n) => n.notebook_id === notebookId)?.title || "Financial Statement Analysis";
  const maxFileSizeMb = user?.quota.max_file_size_mb ?? guestQuota?.max_file_size_mb ?? 5;

  const docs = useDocuments(notebookId, maxSources, maxFileSizeMb, showToast, onLoginRequired);
  const chat = useChat({
    notebookId,
    selectedDocIds: docs.selectedDocIds,
    maxSources,
    showToast,
    onLoginRequired,
    onTitle: (id, title) => setNotebooks((prev) => prev.map((n) => (n.notebook_id === id ? { ...n, title } : n))),
  });

  // While any chat still processes files, refresh the list so its spinner clears (and the delete button returns) without a reload
  const isProcessing = isAuthenticated && (notebooks.some((n) => n.processing_count) || docs.documents.some(isDocProcessing));
  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(() => void attempt(notebookService.list()).then((list) => list && setNotebooks(list)), REFRESH_WHILE_PROCESSING_MS);
    return () => clearInterval(timer);
  }, [isProcessing]);

  const openNotebook = async (notebook: Notebook) => {
    const id = notebook.notebook_id;
    opening.current = id;
    setNotebookId(id);
    docs.reset();
    chat.setMessages([]);
    const [documents, messages] = await Promise.all([attempt(documentService.list(id)), attempt(chatService.getMessages(id))]);
    if (opening.current !== id) return;  // the user already opened another chat
    if (documents) docs.load(documents);
    if (messages) chat.setMessages(messages);
  };

  const selectNotebook = (id: string) => {
    if (id !== notebookId) navigate(`/app/${id}`);
  };

  const newChat = async () => {
    if (!isAuthenticated) {
      showToast("Please sign in to create new analysis sessions and save history!", "warning", "Sign in now", onLoginRequired);
      return;
    }
    try {
      navigate(`/app/${(await emptyOrNewNotebook()).notebook_id}`);
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to create new session." : "Connection error when creating session.", "error");
    }
  };

  const renameNotebook = async (id: string, title: string): Promise<boolean> => {
    try {
      await notebookService.rename(id, title);
      setNotebooks((prev) => prev.map((n) => (n.notebook_id === id ? { ...n, title } : n)));
      return true;
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to rename session." : "Connection error when renaming session.", "error");
      return false;
    }
  };

  const deleteNotebook = async (id: string) => {
    try {
      await notebookService.remove(id);
      showToast("Session deleted successfully.", "info");
      if (id === notebookId) navigate("/app");
      else setNotebooks((prev) => prev.filter((n) => n.notebook_id !== id));
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to delete session." : "Connection error when deleting session.", "error");
    }
  };

  useEffect(() => {
    if (isAuthLoading) return;  // until the token is checked a member looks like a guest and would open a guest notebook

    const loadMemberData = async () => {
      const list = await attempt(notebookService.list());
      if (!list) return;
      setNotebooks(list);
      if (!routeNotebookId) {  // /app: continue the latest chat (the list is newest first), or start the first one
        navigate(`/app/${(list[0] ?? (await emptyOrNewNotebook())).notebook_id}`, { replace: true });
        return;
      }
      const notebook = list.find((n) => n.notebook_id === routeNotebookId);
      if (notebook) {
        await openNotebook(notebook);
      } else {
        showToast("This analysis session does not exist or is no longer available.", "warning");
        navigate("/app", { replace: true });
      }
    };

    const loadGuestData = async () => {
      if (routeNotebookId) {  // the id of a guest notebook is its key: it never goes in the URL
        navigate("/app", { replace: true });
        return;
      }
      const notebook = await guestNotebook();
      if (!notebook) {
        docs.reset();
        chat.setMessages([]);
        return;
      }
      setNotebooks([notebook]);
      await openNotebook(notebook);
    };

    const load = isAuthenticated ? loadMemberData : loadGuestData;
    load().catch((err) => {
      if (err instanceof ApiError && err.status === 429 && err.detail) showToast(err.detail, "warning");
      else console.warn("Unable to load workspace data:", err);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isAuthLoading, routeNotebookId]);

  return {
    toast, showToast, closeToast, notebookTitle, isAuthenticated, maxSources, maxFileSizeMb, docs, chat,
    notebooks, notebookId, selectNotebook, newChat, renameNotebook, deleteNotebook,
  };
}
