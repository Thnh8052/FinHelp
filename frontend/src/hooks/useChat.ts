import { useCallback, useState } from "react";
import { ApiError } from "../services/api";
import { chatService } from "../services/chat";
import { guestStore } from "../services/notebooks";
import { ChatMessage, ChatSession } from "../types/chat";
import { ShowToast } from "./useToast";

interface ChatOptions {
  notebookId: string;
  isAuthenticated: boolean;
  selectedDocIds: string[];
  maxSources: number;
  showToast: ShowToast;
  onLoginRequired: () => void;
}

/** Các đoạn chat của notebook, tin nhắn của đoạn đang mở, và gửi câu hỏi (khách chỉ được 1 tài liệu nguồn). */
export function useChat({ notebookId, isAuthenticated, selectedDocIds, maxSources, showToast, onLoginRequired }: ChatOptions) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loginWarning = (detail: string) => showToast(detail, "warning", "Sign in now", onLoginRequired);

  const newChat = async () => {
    if (!isAuthenticated) {
      showToast("Please sign in to create new analysis sessions and save history!", "warning", "Sign in now", onLoginRequired);
      return;
    }
    try {
      const session = await chatService.createSession(notebookId, "New Financial Session");
      setSessions((prev) => [session, ...prev]);
      setCurrentSessionId(session.session_id);
      setMessages([]);
      showToast("New analysis session created.", "success");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to create new session." : "Connection error when creating session.", "error");
    }
  };

  const selectSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsLoading(true);
    try {
      setMessages(await chatService.getMessages(sessionId));
    } catch {
      showToast("Unable to load messages for this session.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  const deleteSession = async (sessionId: string) => {
    try {
      await chatService.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      if (currentSessionId === sessionId) {
        const remaining = sessions.filter((s) => s.session_id !== sessionId);
        if (remaining.length > 0) {
          selectSession(remaining[0].session_id);
        } else {
          setCurrentSessionId(null);
          setMessages([]);
        }
      }
      showToast("Session deleted successfully.", "info");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Unable to delete session." : "Connection error when deleting session.", "error");
    }
  };

  const sendMessage = async (queryText: string, mentions?: string[]) => {
    if (selectedDocIds.length === 0) {
      showToast("Please select at least one filing from the sources drawer before querying.", "warning");
      return;
    }
    const assistantNote = (id: string, content: string): ChatMessage => ({
      message_id: `${id}_${Date.now()}`,
      session_id: currentSessionId || "ses_err",
      role: "assistant",
      content,
      created_at: new Date().toISOString(),
    });
    setMessages((prev) => [
      ...prev,
      {
        message_id: `msg_user_${Date.now()}`,
        session_id: currentSessionId || "ses_active",
        role: "user",
        content: queryText,
        created_at: new Date().toISOString(),
      },
    ]);
    setIsLoading(true);

    try {
      const data = await chatService.query({
        notebook_id: notebookId,
        session_id: currentSessionId,
        query: queryText,
        document_ids: Array.from(new Set([...(mentions || []), ...selectedDocIds])).slice(0, maxSources),
        mentions,
      });
      setMessages((prev) => [
        ...prev,
        {
          message_id: `msg_asst_${Date.now()}`,
          session_id: data.session_id,
          role: "assistant",
          content: data.answer,
          citations: data.citations || [],
          created_at: new Date().toISOString(),
          understood: data.understood || "",
          alternatives: data.alternatives || [],
          query: queryText,
        },
      ]);

      // Backend sinh session_id mới và chưa có trong danh sách đoạn chat
      if (data.session_id && data.session_id !== currentSessionId) {
        setCurrentSessionId(data.session_id);
        if (!isAuthenticated) guestStore.setSession(data.session_id);
        setSessions((prev) =>
          prev.some((s) => s.session_id === data.session_id)
            ? prev
            : [{ session_id: data.session_id, notebook_id: notebookId, title: queryText.slice(0, 36) }, ...prev]
        );
      }
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail || `Server error (HTTP ${err.status})`;
        // Auth required
        if (err.status === 403 || detail.toLowerCase().includes("login") || detail.toLowerCase().includes("sign in") || detail.toLowerCase().includes("đăng nhập")) {
          loginWarning(detail);
        } else {
          showToast(detail, "error");
        }
        setMessages((prev) => [...prev, assistantNote("msg_err", `⚠️ ${detail}`)]);
      } else {
        showToast("Unable to connect to backend server.", "error");
        setMessages((prev) => [
          ...prev,
          assistantNote("msg_err", "⚠️ Unable to connect to server. Please check your network connection."),
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return {
    sessions, setSessions, messages, setMessages, currentSessionId, setCurrentSessionId, isLoading,
    newChat, selectSession, deleteSession, sendMessage,
  };
}
