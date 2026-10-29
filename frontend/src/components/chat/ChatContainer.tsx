import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, CitationItem, MentionOption } from "../../types/chat";
import { CitationBadge } from "./CitationBadge";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CheckIcon, ChevronRightIcon, CopyIcon, SendIcon } from "../common/Icons";
import "./chat.css";

interface ChatContainerProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, mentions?: string[]) => void;
  isLoading: boolean;
  onSelectCitation: (citation: CitationItem) => void;
  onClearChat?: () => void;
  sessionTitle?: string;
  onNewChat?: () => void;
  onOpenSources?: () => void;
  onToggleSources?: () => void;
  isSourcesOpen?: boolean;
  /** Chưa chọn tài liệu nguồn: không cho gửi (hệ thống không tự đoán phạm vi). */
  hasSources?: boolean;
  /** Tài liệu nguồn đã chọn, để tag bằng @ (câu hỏi chỉ về các tài liệu được tag). */
  mentionOptions?: MentionOption[];
}

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  onSendMessage,
  isLoading,
  onSelectCitation,
  sessionTitle,
  onNewChat: _onNewChat,
  onOpenSources,
  onToggleSources,
  isSourcesOpen = false,
  hasSources = true,
  mentionOptions = [],
}) => {
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // "@" vừa gõ ở cuối ô nhập: hiện danh sách tài liệu nguồn để chọn
  const mentionQuery = /(?:^|\s)@([^\s@]*)$/.exec(input)?.[1];
  const mentionMatches =
    mentionQuery === undefined
      ? []
      : mentionOptions.filter(
          (o) => !mentions.includes(o.document_id) && o.label.toLowerCase().includes(mentionQuery.toLowerCase())
        );
  const pickMention = (o: MentionOption) => {
    setMentions([...mentions, o.document_id]);
    setInput(input.replace(/@[^\s@]*$/, ""));
  };
  const labelOf = (id: string) => mentionOptions.find((o) => o.document_id === id)?.label || id;
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Tự động mở rộng độ cao thanh chat theo nội dung (Gemini & NotebookLM style)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      // Min 26px (1 dòng), mở rộng tối đa 220px (~8-9 dòng), cuộn êm khi vượt quá
      const newHeight = Math.min(Math.max(scrollHeight, 26), 220);
      textareaRef.current.style.height = `${newHeight}px`;
    }
  }, [input]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading || !hasSources) return;
    const toSend = input;
    const usedMentions = mentions.length > 0 ? mentions : undefined;
    setInput("");
    setMentions([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "26px";
    }
    onSendMessage(toSend, usedMentions);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleCopy = (content: string, msgId: string) => {
    navigator.clipboard.writeText(content);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const samplePrompts = [
    "So sánh Doanh thu (Total Revenue) giữa các kỳ gần nhất",
    "Biên lợi nhuận hoạt động (Operating Margin) đạt bao nhiêu?",
    "Phân tích Đòn bẩy tài chính và Nợ dài hạn (Long-term Debt)",
    "Tóm tắt các rủi ro trọng yếu (Risk Factors) trong BCTC",
  ];

  const canSubmit = !isLoading && hasSources && !!input.trim();

  return (
    <div className="chat-container">
      {/* Top Header Bar inside Chat Container: Context Bar Tinh Gọn (Mockup V3) */}
      <div className="chat-header">
        <div className="chat-header-title-box">
          <span className="chat-header-title">
            {sessionTitle || "Đoạn chat hiện tại"}
          </span>
        </div>

        {/* Thanh Context hiển thị các nguồn đang được chọn để hỏi */}
        <div className="chat-header-sources">
          <span className="chat-sources-label">Đang hỏi trên:</span>
          <div className="chat-sources-tags">
            {mentionOptions && mentionOptions.length > 0 ? (
              mentionOptions.map((opt) => (
                <span key={opt.document_id} className="chat-source-tag">
                  {opt.label}
                </span>
              ))
            ) : (
              <span className="chat-source-tag muted">Chưa chọn nguồn</span>
            )}
          </div>
          {(onToggleSources || onOpenSources) && (
            <button
              type="button"
              onClick={onToggleSources || onOpenSources}
              className={`chat-manage-sources-btn ${isSourcesOpen ? "active" : ""}`}
              title={isSourcesOpen ? "Đóng danh sách quản lý BCTC" : "Mở danh sách quản lý BCTC"}
            >
              <span>{isSourcesOpen ? "Đóng quản lý nguồn" : "Quản lý nguồn"}</span>
              <ChevronRightIcon size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Messages Stream (Centered ChatGPT / Claude reading column) */}
      <div className="chat-messages-stream">
        <div className="chat-messages-column">
          {messages.length === 0 && !isLoading && (
            <div className="chat-empty-state">
              <div className="chat-empty-title">
                Sẵn sàng phân tích Báo cáo tài chính
              </div>
              <p className="chat-empty-desc">
                Hãy chọn hoặc tải lên báo cáo tài chính (PDF SEC Form 10-K / 10-Q), sau đó đặt câu hỏi về chỉ số tài chính, doanh thu, lợi nhuận hoặc đối chiếu kiểm toán.
              </p>
            </div>
          )}
          {messages.map((msg) => {
            const isUser = msg.role === "user";

            return (
              <div
                key={msg.message_id}
                className={`chat-message-row ${isUser ? "user" : "assistant"}`}
              >
                {/* Sender label */}
                <span className="chat-sender-label">
                  {isUser ? "Bạn" : "FinAnalyst"}
                </span>

                {/* Message Box */}
                <div className={`chat-message-bubble ${isUser ? "user" : "assistant"}`}>
                  {!isUser && msg.understood && <div className="chat-understood">{msg.understood}</div>}
                  {isUser ? (
                    <div className="chat-message-text">{msg.content}</div>
                  ) : (
                    <MarkdownRenderer
                      content={msg.content}
                      citations={msg.citations}
                      onSelectCitation={onSelectCitation}
                    />
                  )}
                  {!isUser && msg.alternatives && msg.alternatives.length > 0 && msg.query && (
                    <div className="chat-alternatives">
                      {msg.alternatives.map((a) => (
                        <button
                          key={a.document_id}
                          type="button"
                          className="chat-sample-btn"
                          disabled={isLoading}
                          onClick={() => onSendMessage(msg.query!, [a.document_id])}
                        >
                          Hỏi lại với {a.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Grounded Evidence Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="chat-citations-container">
                      <div className="chat-citations-title">
                        Nguồn đối chiếu ({msg.citations.length}):
                      </div>
                      <div className="chat-citations-list">
                        {msg.citations.map((cite, idx) => (
                          <CitationBadge
                            key={cite.citation_id}
                            citation={cite}
                            index={idx + 1}
                            onClick={() => onSelectCitation(cite)}
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Actions: Copy */}
                  {!isUser && (
                    <div className="chat-message-actions">
                      <button
                        onClick={() => handleCopy(msg.content, msg.message_id)}
                        className="chat-copy-btn"
                        title="Sao chép câu trả lời"
                      >
                        {copiedMsgId === msg.message_id ? (
                          <>
                            <CheckIcon size={12} color="#10b981" />
                            <span className="chat-copied-text">Đã sao chép</span>
                          </>
                        ) : (
                          <>
                            <CopyIcon size={12} />
                            <span>Sao chép</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Assistant Typing / Streaming Skeleton */}
          {isLoading && (
            <div className="chat-loading-row">
              <span className="chat-sender-label">FinAnalyst</span>
              <div className="chat-loading-bubble">
                <div className="chat-loading-spinner" />
                <span>Đang tra cứu dữ liệu BCTC và lập luận đối chiếu...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Prompt Input Box (ChatGPT / Claude Style) */}
      <div className="chat-input-wrapper">
        <div className="chat-input-column">
          {/* Quick suggestions when input is empty (Điền vào textarea thay vì gửi ngay) */}
          {messages.length <= 3 && (
            <div className="chat-sample-prompts">
              <span className="chat-prompts-label">Gợi ý:</span>
              {samplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setInput(p);
                    textareaRef.current?.focus();
                  }}
                  disabled={isLoading || !hasSources}
                  className="chat-sample-btn"
                  title="Điền câu hỏi mẫu vào ô nhập"
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Tài liệu đã tag bằng @ (câu hỏi chỉ về các tài liệu này) */}
          {(mentions.length > 0 || mentionMatches.length > 0) && (
            <div className="chat-mentions">
              {mentions.map((id) => (
                <span key={id} className="chat-mention-chip">
                  @{labelOf(id)}
                  <button type="button" aria-label="Bỏ tag" onClick={() => setMentions(mentions.filter((m) => m !== id))}>
                    ×
                  </button>
                </span>
              ))}
              {mentionMatches.map((o) => (
                <button key={o.document_id} type="button" className="chat-mention-option" onClick={() => pickMention(o)}>
                  @{o.label}
                </button>
              ))}
            </div>
          )}

          {/* Clean Input Pill Container */}
          <form onSubmit={handleSubmit} className="chat-input-form">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                hasSources
                  ? "Đặt câu hỏi về BCTC (ví dụ: So sánh doanh thu và tính tốc độ tăng trưởng)..."
                  : "Hãy chọn tài liệu nguồn ở thanh bên phải trước khi đặt câu hỏi"
              }
              disabled={isLoading || !hasSources}
              rows={1}
              className="chat-input-textarea"
            />

            <button
              type="submit"
              disabled={!canSubmit}
              aria-label="Gửi"
              className={`chat-send-btn ${canSubmit ? "active" : "inactive"}`}
            >
              <SendIcon size={14} />
            </button>
          </form>

          <div className="chat-input-hint">
            Nhấn Enter để gửi • Shift + Enter để xuống dòng • Gõ @ để chỉ định tài liệu
          </div>
        </div>
      </div>
    </div>
  );
};
