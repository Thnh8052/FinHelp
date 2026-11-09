import { useState } from "react";
import { ApiError } from "../services/api";
import { chatService } from "../services/chat";
import { ChatMessage } from "../types/chat";
import { ShowToast } from "./useToast";

interface ChatOptions {
  notebookId: string;
  selectedDocIds: string[];
  maxSources: number;
  showToast: ShowToast;
  onLoginRequired: () => void;
  onTitle: (notebookId: string, title: string) => void;
}

/** Tin nhắn của đoạn chat đang mở (mỗi notebook là một đoạn chat) và gửi câu hỏi (khách chỉ được 1 tài liệu nguồn). */
export function useChat({ notebookId, selectedDocIds, maxSources, showToast, onLoginRequired, onTitle }: ChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loginWarning = (detail: string) => showToast(detail, "warning", "Sign in now", onLoginRequired);

  const sendMessage = async (queryText: string, mentions?: string[]) => {
    if (selectedDocIds.length === 0) {
      showToast("Please select at least one filing from the sources drawer before querying.", "warning");
      return;
    }
    const assistantNote = (id: string, content: string): ChatMessage => ({
      message_id: `${id}_${Date.now()}`,
      notebook_id: notebookId,
      role: "assistant",
      content,
      created_at: new Date().toISOString(),
    });
    setMessages((prev) => [
      ...prev,
      {
        message_id: `msg_user_${Date.now()}`,
        notebook_id: notebookId,
        role: "user",
        content: queryText,
        created_at: new Date().toISOString(),
      },
    ]);
    setIsLoading(true);

    try {
      const data = await chatService.query({
        notebook_id: notebookId,
        query: queryText,
        document_ids: Array.from(new Set([...(mentions || []), ...selectedDocIds])).slice(0, maxSources),
        mentions,
      });
      setMessages((prev) => [
        ...prev,
        {
          message_id: `msg_asst_${Date.now()}`,
          notebook_id: notebookId,
          role: "assistant",
          content: data.answer,
          citations: data.citations || [],
          created_at: new Date().toISOString(),
          understood: data.understood || "",
          alternatives: data.alternatives || [],
          query: queryText,
        },
      ]);
      onTitle(notebookId, data.title);
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

  return { messages, setMessages, isLoading, sendMessage };
}
