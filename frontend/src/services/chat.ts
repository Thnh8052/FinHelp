import { apiRequest } from "./api";
import { ChatMessage, CitationItem } from "../types/chat";

/** Tin nhắn như backend lưu (MessageRecord); phần hiểu câu hỏi nằm trong trace_info. */
interface MessageDto {
  message_id: string;
  notebook_id: string;
  role: ChatMessage["role"];
  content: string;
  citations?: CitationItem[];
  trace_info?: { understood?: string; alternatives?: ChatMessage["alternatives"] };
  created_at: string;
}

const toChatMessage = (m: MessageDto): ChatMessage => ({
  message_id: m.message_id,
  notebook_id: m.notebook_id,
  role: m.role,
  content: m.content,
  citations: m.citations || [],
  understood: m.trace_info?.understood || "",
  alternatives: m.trace_info?.alternatives || [],
  created_at: m.created_at,
});

export interface QueryRequest {
  notebook_id: string;
  query: string;
  document_ids: string[];
  mentions?: string[];
}

export interface QueryResponse {
  title: string;
  query: string;
  answer: string;
  intent: string;
  citations: CitationItem[];
  understood?: string;
  alternatives?: ChatMessage["alternatives"];
}

export const chatService = {
  getMessages: async (notebookId: string): Promise<ChatMessage[]> =>
    (await apiRequest<MessageDto[]>(`/chat/messages/${notebookId}`)).map(toChatMessage),

  query: (body: QueryRequest) => apiRequest<QueryResponse>("/chat/query", { method: "POST", body: JSON.stringify(body) }),
};
