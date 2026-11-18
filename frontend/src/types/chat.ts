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
   * tin nhắn cũ không có trường này thì hỏi lại với riêng tài liệu đó. `kind`: nút "tìm kỹ hơn" dưới câu trả lời chưa đạt (một file / mọi nguồn đã chọn),
   * chỉ bấm được một lần (docs/Version_3/fail_cases.md, S3). */
  alternatives?: { document_id: string; label: string; document_ids?: string[]; kind?: "retry_one" | "retry_all" }[];
  /** Các nút dưới câu trả lời (từ 17/11/2026; tin nhắn cũ dùng `alternatives`). */
  actions?: AnswerActions;
  /** Câu hỏi đã gửi (để hỏi lại với tài liệu khác). */
  query?: string;
  /** Có trường này (kể cả null) = câu trả lời đã lưu, báo sai được; -1 = người dùng đã báo sai số liệu. */
  user_rating?: number | null;
  /** Câu trả lời đang được viết (chat dạng stream): chưa có trích dẫn, chưa sao chép được. */
  streaming?: boolean;
}

/** Nút dưới câu trả lời (backend orchestrator.answer_actions; docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md mục 4.2).
 * `chooser`: mọi tài liệu đã chọn, tài liệu câu trả lời đã dùng được đánh dấu sẵn; chọn được nhiều tài liệu rồi hỏi lại (chúng thành thẻ @).
 * `search_more`: tìm lại đủ các bước, bỏ qua các đoạn đã gửi; `prominent` khi câu trả lời hụt hoặc hệ thống phải bỏ bớt một bước.
 * `edit_question`: đưa câu hỏi về ô nhập để sửa. `try_again`: hỏi lại y nguyên (sau khi hệ thống chưa tạo được câu trả lời).
 * Mỗi câu trả lời chỉ bấm được một lần (chooser, search_more hoặc try_again). */
export interface AnswerActions {
  chooser?: { document_id: string; label: string; checked: boolean }[];
  search_more?: { prominent: boolean } | null;
  edit_question?: boolean;
  try_again?: boolean;
}

export type ChatStage = "understanding" | "searching" | "writing" | "checking";

/** Một tài liệu nguồn có thể tag bằng @ trong ô chat. */
export interface MentionOption {
  document_id: string;
  label: string;
}

