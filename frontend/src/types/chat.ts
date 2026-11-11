export interface CitationItem {
  citation_id: string;
  document_id: string;
  page: number;
  snippet: string;
  /** Câu trả lời có dùng đoạn này ([n]) hay không; không có thì hiện như đã được dùng. */
  cited?: boolean | null;
}

export interface ChatMessage {
  message_id: string;
  notebook_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: CitationItem[];
  created_at: string;
  /** Cách hệ thống hiểu câu hỏi (tài liệu, giả định), hiện phía trên câu trả lời. */
  understood?: string;
  /** Tài liệu khác cũng khớp: bấm để hỏi lại với tài liệu đó. */
  alternatives?: { document_id: string; label: string }[];
  /** Câu hỏi đã gửi (để hỏi lại với tài liệu khác). */
  query?: string;
  /** Câu trả lời đang được viết (chat dạng stream): chưa có trích dẫn, chưa sao chép được. */
  streaming?: boolean;
}

export type ChatStage = "understanding" | "searching" | "writing" | "checking";

/** Một tài liệu nguồn có thể tag bằng @ trong ô chat. */
export interface MentionOption {
  document_id: string;
  label: string;
}

