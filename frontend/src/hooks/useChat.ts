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

  const loginWarning = (detail: string) => showToast(detail, "warning", "Đăng nhập ngay", onLoginRequired);

  const newChat = async () => {
    if (!isAuthenticated) {
      showToast("Bạn cần đăng nhập để tạo thêm đoạn chat mới và lưu trữ lịch sử!", "warning", "Đăng nhập ngay", onLoginRequired);
      return;
    }
    try {
      const session = await chatService.createSession(notebookId, "Hội thoại tài chính mới");
      setSessions((prev) => [session, ...prev]);
      setCurrentSessionId(session.session_id);
      setMessages([]);
      showToast("Đã tạo đoạn chat mới thành công.", "success");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Không thể tạo đoạn chat mới." : "Lỗi kết nối khi tạo đoạn chat mới.", "error");
    }
  };

  const selectSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsLoading(true);
    try {
      setMessages(await chatService.getMessages(sessionId));
    } catch {
      showToast("Không thể tải tin nhắn của đoạn chat này.", "error");
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
      showToast("Đã xóa đoạn chat thành công.", "info");
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail || "Không thể xóa đoạn chat." : "Lỗi kết nối khi xóa đoạn chat.", "error");
    }
  };

  const sendMessage = async (queryText: string, mentions?: string[]) => {
    if (selectedDocIds.length === 0) {
      showToast("Hãy chọn ít nhất một tài liệu nguồn (thanh tài liệu phía trên) rồi đặt câu hỏi.", "warning");
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
        const detail = err.detail || `Lỗi máy chủ (HTTP ${err.status})`;
        // Cần đăng nhập (ví dụ hỏi trong notebook của người dùng): thông báo kèm nút đăng nhập
        if (err.status === 403 || detail.toLowerCase().includes("đăng nhập")) loginWarning(detail);
        else showToast(detail, "error");
        setMessages((prev) => [...prev, assistantNote("msg_err", `⚠️ ${detail}`)]);
      } else {
        showToast("Không thể kết nối đến máy chủ hệ thống.", "error");
        setMessages((prev) => [
          ...prev,
          assistantNote("msg_err", "⚠️ Không thể kết nối đến máy chủ hệ thống. Vui lòng kiểm tra lại đường truyền."),
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
