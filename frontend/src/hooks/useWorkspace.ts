import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { chatService } from "../services/chat";
import { documentService } from "../services/documents";
import { guestNotebookId, guestStore, notebookService } from "../services/notebooks";
import { authService } from "../services/auth";
import { useChat } from "./useChat";
import { useDocuments } from "./useDocuments";
import { useToast } from "./useToast";

const MAX_SOURCES_GUEST = 1;
const MAX_SOURCES_USER = 5;

/** Một bước tải có thể hỏng mà không chặn các bước sau (null khi hỏng). */
const attempt = <T,>(p: Promise<T>): Promise<T | null> => p.catch(() => null);

/**
 * Không gian làm việc: notebook, tài liệu và đoạn chat theo trạng thái đăng nhập.
 * Người dùng đăng nhập: notebook đầu tiên của họ, đoạn chat đầu tiên. Khách: notebook riêng do backend cấp (phiên chat tạo ở câu hỏi đầu).
 */
export function useWorkspace(onLoginRequired: () => void) {
  const { isAuthenticated } = useAuth();
  const { toast, showToast, closeToast } = useToast();
  const [notebookTitle, setNotebookTitle] = useState("Phân Tích Báo Cáo Tài Chính");
  const [notebookId, setNotebookId] = useState("");
  const maxSources = isAuthenticated ? MAX_SOURCES_USER : MAX_SOURCES_GUEST;

  const docs = useDocuments(notebookId, maxSources, showToast, onLoginRequired);
  const chat = useChat({ notebookId, isAuthenticated, selectedDocIds: docs.selectedDocIds, maxSources, showToast, onLoginRequired });

  useEffect(() => {
    const loadMemberData = async () => {
      const notebooks = await attempt(notebookService.list());
      if (!notebooks || notebooks.length === 0) return;
      const nb = notebooks[0];
      setNotebookId(nb.notebook_id);
      setNotebookTitle(nb.title);

      const documents = await attempt(documentService.list(nb.notebook_id));
      if (documents) docs.load(documents);

      const sessions = await attempt(chatService.listSessions(nb.notebook_id));
      if (!sessions) return;
      chat.setSessions(sessions);
      if (sessions.length === 0) {
        chat.setCurrentSessionId(null);
        chat.setMessages([]);
        return;
      }
      chat.setCurrentSessionId(sessions[0].session_id);
      const messages = await attempt(chatService.getMessages(sessions[0].session_id));
      if (messages) chat.setMessages(messages);
    };

    const loadGuestData = async () => {
      setNotebookTitle("Không Gian Dùng Thử (Khách Chưa Đăng Nhập)");
      docs.reset();
      chat.setMessages([]);
      try {
        const guestNb = await guestNotebookId();
        if (!guestNb) throw new Error("guest notebook");
        setNotebookId(guestNb);
        const guestSession = guestStore.session();
        chat.setCurrentSessionId(guestSession);
        chat.setSessions(guestSession ? [{ session_id: guestSession, notebook_id: guestNb, title: "Phiên dùng thử (Khách)" }] : []);

        const documents = await attempt(documentService.list(guestNb));
        if (documents) docs.load(documents);

        if (guestSession) {
          const messages = await attempt(chatService.getMessages(guestSession));
          if (messages) {
            chat.setMessages(messages);
          } else {  // phiên đã lưu không còn dùng được
            guestStore.setSession(null);
            chat.setCurrentSessionId(null);
            chat.setSessions([]);
          }
        }
      } catch {
        docs.reset();
        chat.setMessages([]);
      }
    };

    const load = isAuthenticated && authService.getAuthToken() ? loadMemberData : loadGuestData;
    load().catch((err) => console.warn("Không thể tải dữ liệu không gian làm việc:", err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  return { toast, showToast, closeToast, notebookTitle, isAuthenticated, maxSources, docs, chat };
}
