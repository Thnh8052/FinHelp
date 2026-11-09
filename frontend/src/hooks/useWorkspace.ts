import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../services/api";
import { chatService } from "../services/chat";
import { documentService } from "../services/documents";
import { activeNotebookStore, guestNotebook, notebookService } from "../services/notebooks";
import { authService } from "../services/auth";
import { Notebook } from "../types/notebook";
import { useChat } from "./useChat";
import { useDocuments } from "./useDocuments";
import { useToast } from "./useToast";

const MAX_SOURCES_GUEST = 1;
const MAX_SOURCES_USER = 5;

/** Một bước tải có thể hỏng mà không chặn các bước sau (null khi hỏng). */
const attempt = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null);

/**
 * Không gian làm việc: danh sách đoạn chat (mỗi notebook là một đoạn chat), tài liệu và tin nhắn của đoạn đang mở.
 * Người dùng đăng nhập: mở lại đoạn đang dùng trước đó. Khách: một notebook riêng do backend cấp.
 */
export function useWorkspace(onLoginRequired: () => void) {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const { toast, showToast, closeToast } = useToast();
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [notebookId, setNotebookId] = useState("");
  const opening = useRef("");
  const maxSources = isAuthenticated ? MAX_SOURCES_USER : MAX_SOURCES_GUEST;

  const notebookTitle = notebooks.find((n) => n.notebook_id === notebookId)?.title || "Financial Statement Analysis";

  const docs = useDocuments(notebookId, maxSources, showToast, onLoginRequired);
  const chat = useChat({
    notebookId,
    selectedDocIds: docs.selectedDocIds,
    maxSources,
    showToast,
    onLoginRequired,
    onTitle: (id, title) => setNotebooks((prev) => prev.map((n) => (n.notebook_id === id ? { ...n, title } : n))),
  });

  const openNotebook = async (notebook: Notebook) => {
    const id = notebook.notebook_id;
    opening.current = id;
    setNotebookId(id);
    activeNotebookStore.set(id);
    docs.reset();
    chat.setMessages([]);
    const [documents, messages] = await Promise.all([attempt(documentService.list(id)), attempt(chatService.getMessages(id))]);
    if (opening.current !== id) return;  // the user already opened another chat
    if (documents) docs.load(documents);
    if (messages) chat.setMessages(messages);
  };

  const selectNotebook = (id: string) => {
    const notebook = notebooks.find((n) => n.notebook_id === id);
    if (notebook && id !== notebookId) void openNotebook(notebook);
  };

  const newChat = async () => {
    if (!isAuthenticated) {
      showToast("Please sign in to create new analysis sessions and save history!", "warning", "Sign in now", onLoginRequired);
      return;
    }
    try {
      const notebook = await notebookService.create();
      setNotebooks((prev) => [notebook, ...prev]);
      await openNotebook(notebook);
      showToast("New analysis session created.", "success");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to create new session." : "Connection error when creating session.", "error");
    }
  };

  const deleteNotebook = async (id: string) => {
    try {
      await notebookService.remove(id);
      let remaining = notebooks.filter((n) => n.notebook_id !== id);
      if (remaining.length === 0) remaining = await notebookService.list();  // the backend gives a member their first chat again
      setNotebooks(remaining);
      if (id === notebookId && remaining.length > 0) await openNotebook(remaining[0]);
      showToast("Session deleted successfully.", "info");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to delete session." : "Connection error when deleting session.", "error");
    }
  };

  useEffect(() => {
    if (isAuthLoading) return;  // until the token is checked a member looks like a guest and would open a guest notebook

    const loadMemberData = async () => {
      const list = await attempt(notebookService.list());
      if (!list || list.length === 0) return;
      setNotebooks(list);
      const saved = activeNotebookStore.get();
      await openNotebook(list.find((n) => n.notebook_id === saved) || list[0]);
    };

    const loadGuestData = async () => {
      const notebook = await guestNotebook();
      if (!notebook) {
        docs.reset();
        chat.setMessages([]);
        return;
      }
      setNotebooks([notebook]);
      await openNotebook(notebook);
    };

    const load = isAuthenticated && authService.getAuthToken() ? loadMemberData : loadGuestData;
    load().catch((err) => console.warn("Unable to load workspace data:", err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isAuthLoading]);

  return {
    toast, showToast, closeToast, notebookTitle, isAuthenticated, maxSources, docs, chat,
    notebooks, notebookId, selectNotebook, newChat, deleteNotebook,
  };
}
