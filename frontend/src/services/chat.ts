import { apiRequest } from "./api";
import { ChatMessage, ChatSession, CitationItem } from "../types/chat";

/** Tin nhắn như backend lưu (MessageRecord); phần hiểu câu hỏi nằm trong trace_info. */
interface MessageDto {
  message_id: string;
  session_id: string;
  role: ChatMessage["role"];
  content: string;
  citations?: CitationItem[];
  trace_info?: { understood?: string; alternatives?: ChatMessage["alternatives"] };
  created_at: string;
}

const toChatMessage = (m: MessageDto): ChatMessage => ({
  message_id: m.message_id,
  session_id: m.session_id,
  role: m.role,
  content: m.content,
  citations: m.citations || [],
  understood: m.trace_info?.understood || "",
  alternatives: m.trace_info?.alternatives || [],
  created_at: m.created_at,
});

export interface QueryRequest {
  notebook_id: string;
  session_id: string | null;
  query: string;
  document_ids: string[];
  mentions?: string[];
}

export interface QueryResponse {
  session_id: string;
  query: string;
  answer: string;
  intent: string;
  citations: CitationItem[];
  understood?: string;
  alternatives?: ChatMessage["alternatives"];
}

export const chatService = {
  listSessions: (notebookId: string) => apiRequest<ChatSession[]>(`/chat/sessions/notebook/${notebookId}`),

  getMessages: async (sessionId: string): Promise<ChatMessage[]> =>
    (await apiRequest<MessageDto[]>(`/chat/sessions/${sessionId}/messages`)).map(toChatMessage),

  createSession: (notebookId: string, title: string) =>
    apiRequest<ChatSession>("/chat/sessions", { method: "POST", body: JSON.stringify({ notebook_id: notebookId, title }) }),

  deleteSession: (sessionId: string) => apiRequest<{ success: boolean }>(`/chat/sessions/${sessionId}`, { method: "DELETE" }),

  query: (body: QueryRequest) => apiRequest<QueryResponse>("/chat/query", { method: "POST", body: JSON.stringify(body) }),
};
