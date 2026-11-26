export interface CitationItem {
  citation_id: string;
  document_id: string;
  page: number;
  snippet: string;
  /** Câu trả lời có dùng đoạn này ([n]) hay không; không có thì hiện như đã được dùng. */
  cited?: boolean | null;
  /** Một bảng ở trang này có thể đọc chưa chuẩn (kiểm lúc tải lên): thẻ trích dẫn nhắc xem trang gốc. */
  may_be_misread?: boolean;
  /** Chữ của trang được nhận dạng từ ảnh trang: thẻ trích dẫn nhắc đối chiếu trang gốc. */
  read_from_image?: boolean;
  /** Đoạn có số liệu đọc từ hình hoặc biểu đồ: thẻ trích dẫn nói rõ. */
  from_figure?: boolean;
  /** Một hình ở trang này chưa đọc được (lúc tải lên): thẻ trích dẫn nói rõ và nhắc xem trang gốc. */
  picture_unread?: boolean;
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
  /** Vị trí trong đoạn chat (0, 1, 2…) của tin đã lưu: để xin trang tin cũ hơn (D7). */
  message_index?: number;
  /** Câu trả lời đang được viết (chat dạng stream): chưa có trích dẫn, chưa sao chép được. */
  streaming?: boolean;
  /** Câu hỏi / câu trả lời do một nút gửi lại (tìm kỹ hơn, thử lại, hỏi lại với tài liệu đã chọn): giao diện gắn nhãn để không trông như câu trùng. */
  click?: ClickKind | "";
  /** Câu trả lời đã được bấm một nút (câu trả lời mới ở bên dưới). */
  clicked?: ClickKind | "";
  /** Số tài liệu đã đánh dấu khi bấm "Hỏi lại" (chỉ có trong phiên đang mở). */
  clickCount?: number;
}

/** Nút dưới câu trả lời (backend orchestrator.answer_actions; docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md mục 4.2).
 * `chooser`: mọi tài liệu đã chọn, tài liệu câu trả lời đã dùng được đánh dấu sẵn; chọn được nhiều tài liệu rồi hỏi lại (chúng thành thẻ @).
 * `search_more`: tìm lại đủ các bước, bỏ qua các đoạn đã gửi; `prominent` khi câu trả lời hụt hoặc hệ thống phải bỏ bớt một bước.
 * `edit_question`: đưa câu hỏi về ô nhập để sửa. `try_again`: hỏi lại y nguyên (sau khi hệ thống chưa tạo được câu trả lời).
 * `search_all`: "Vẫn tìm trong mọi nguồn" sau câu trả lời cố định "các nguồn đã chọn dường như không có thông tin này" (mọi nguồn của câu đó thành thẻ @).
 * Mỗi câu trả lời chỉ bấm được một lần (chooser, search_more, try_again hoặc search_all). */
export type ClickKind = "deeper" | "again" | "chooser" | "everywhere" | "retry";  // retry: stored before 18/11/2026, which button is unknown
/** How a button asks the question again (sent to the server as a flag of the same name); none = over the chooser's ticked sources. */
export type AskMode = "deeper" | "again" | "everywhere";

export interface AnswerActions {
  chooser?: { document_id: string; label: string; checked: boolean }[];
  search_more?: { prominent: boolean } | null;
  edit_question?: boolean;
  try_again?: boolean;
  search_all?: boolean;
  /** The chooser goes above the answer, under the line "the question names no company; I understood it as about ..." (B2, 26/11/2026). */
  chooser_first?: boolean;
}

/** "analyzing": the model of the answer started to think (T6a); the page counts the seconds from there. */
export type ChatStage = "understanding" | "searching" | "writing" | "analyzing" | "checking";

/** Một tài liệu nguồn có thể tag bằng @ trong ô chat. */
export interface MentionOption {
  document_id: string;
  label: string;
}

