import { ApiError, apiRequest, send } from "./api";
import { ChatMessage, ChatStage, CitationItem } from "../types/chat";

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

export interface StreamHandlers {
  onStage: (stage: ChatStage) => void;
  onUnderstood: (text: string, alternatives: ChatMessage["alternatives"]) => void;
  /** The next piece of the answer as it is written; the recorded answer (the resolved value) replaces the pieces. */
  onDelta: (text: string) => void;
}

/** POST /chat/query/stream: server-sent events (stage, understood, delta) ending in done (the recorded answer) or error. */
async function queryStream(body: QueryRequest, on: StreamHandlers): Promise<QueryResponse> {
  const response = await send("/chat/query/stream", { method: "POST", body: JSON.stringify(body) });  // refusals stay JSON errors
  const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const kind = block.match(/^event: (.*)$/m)?.[1];
      const raw = block.match(/^data: (.*)$/m)?.[1];
      if (!kind || raw === undefined) continue;
      const data = JSON.parse(raw);
      if (kind === "stage") on.onStage(data.name);
      else if (kind === "understood") on.onUnderstood(data.text, data.alternatives);
      else if (kind === "delta") on.onDelta(data.text);
      else if (kind === "done") return data as QueryResponse;
      else if (kind === "error") throw new ApiError(data.status, data.code, data.params ?? {});
    }
  }
  throw new TypeError("The answer stream ended early");  // a dropped connection: shown as a connection failure
}

export const chatService = {
  getMessages: (notebookId: string) => apiRequest<ChatMessage[]>(`/chat/messages/${notebookId}`),

  query: (body: QueryRequest) => apiRequest<QueryResponse>("/chat/query", { method: "POST", body: JSON.stringify(body) }),

  queryStream,
};
