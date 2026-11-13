export interface CitationItem {
  citation_id: string;
  document_id: string;
  page: number;
  snippet: string;
  /** Câu trả lời có dùng đoạn này ([n]) hay không; không có thì hiện như đã được dùng. */
  cited?: boolean | null;
  /** Set by the chat when the citation is opened: the numbers the answer states next to this [n], whose lines the PDF viewer marks. */
  figures?: string[];
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
  /** Tài liệu khác cũng khớp: bấm để hỏi lại với tài liệu đó. `document_ids`: cả bộ tài liệu để hỏi lại (chỉ đổi tài liệu này, giữ các công ty khác);
   * tin nhắn cũ không có trường này thì hỏi lại với riêng tài liệu đó. */
  alternatives?: { document_id: string; label: string; document_ids?: string[] }[];
  /** Câu hỏi đã gửi (để hỏi lại với tài liệu khác). */
  query?: string;
  /** Có trường này (kể cả null) = câu trả lời đã lưu, báo sai được; -1 = người dùng đã báo sai số liệu. */
  user_rating?: number | null;
  /** Câu trả lời đang được viết (chat dạng stream): chưa có trích dẫn, chưa sao chép được. */
  streaming?: boolean;
}

export type ChatStage = "understanding" | "searching" | "writing" | "checking";

/** Một tài liệu nguồn có thể tag bằng @ trong ô chat. */
export interface MentionOption {
  document_id: string;
  label: string;
}

