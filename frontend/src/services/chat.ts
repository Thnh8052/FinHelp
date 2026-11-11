import { apiRequest } from "./api";
import { ChatMessage, CitationItem } from "../types/chat";

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
  citations: CitationItem[];
  understood?: string;
  alternatives?: ChatMessage["alternatives"];
}

export const chatService = {
  getMessages: (notebookId: string) => apiRequest<ChatMessage[]>(`/chat/messages/${notebookId}`),

  query: (body: QueryRequest) => apiRequest<QueryResponse>("/chat/query", { method: "POST", body: JSON.stringify(body) }),
};
