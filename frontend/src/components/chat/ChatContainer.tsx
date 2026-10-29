import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, CitationItem, MentionOption } from "../../types/chat";
import { CitationBadge } from "./CitationBadge";
import { CheckIcon, CopyIcon, PlusIcon, SendIcon } from "../common/Icons";
import "./chat.css";

interface ChatContainerProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, mentions?: string[]) => void;
  isLoading: boolean;
  onSelectCitation: (citation: CitationItem) => void;
  onClearChat?: () => void;
  sessionTitle?: string;
  onNewChat?: () => void;
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
  onNewChat,
  hasSources = true,
  mentionOptions = [],
}) => {
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<string[]>([]);
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
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !hasSources) return;
    const tagged = mentions.filter((id) => mentionOptions.some((o) => o.document_id === id));
    onSendMessage(input.trim(), tagged.length ? tagged : undefined);
    setInput("");
    setMentions([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleCopyMessage = (msgId: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const samplePrompts = [
    "So sánh Doanh thu (Total Revenue) giữa 2 kỳ gần nhất",
    "Biên lợi nhuận hoạt động (Operating Margin) đạt bao nhiêu?",
    "Phân tích Đòn bẩy tài chính và Nợ dài hạn (Long-term Debt)",
    "Tóm tắt các rủi ro trọng yếu (Risk Factors) trong Form 10-K",
  ];

  const canSubmit = !isLoading && hasSources && !!input.trim();

  return (
    <div className="chat-container">
      {/* Top Header Bar inside Chat Container (ChatGPT / Claude Style) */}
      <div className="chat-header">
        <div className="chat-header-title-box">
          <span className="chat-header-title">
            {sessionTitle || "Đoạn chat hiện tại"}
          </span>
        </div>

        {onNewChat && (
          <button onClick={onNewChat} className="chat-new-btn">
            <PlusIcon size={13} color="var(--accent-primary)" />
            <span>Thêm đoạn chat mới</span>
          </button>
        )}
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
                  <div className="chat-message-text">{msg.content}</div>
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

                  {/* Citations (NotebookLM / Claude Style) */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="chat-citations-bar">
                      <span className="chat-citations-label">Nguồn:</span>
                      {/* Chỉ hiện đoạn câu trả lời thật sự dùng; số [n] giữ theo vị trí trong danh sách đầy đủ. Không đoạn nào được đánh dấu: hiện hết */}
                      {(msg.citations.some((c) => c.cited) ? msg.citations.filter((c) => c.cited) : msg.citations).map((cite) => (
                        <CitationBadge
                          key={cite.citation_id}
                          citation={cite}
                          index={msg.citations!.indexOf(cite) + 1}
                          onClick={() => onSelectCitation(cite)}
                        />
                      ))}
                    </div>
                  )}

                  {/* Assistant Message Actions (Copy) */}
                  {!isUser && (
                    <div className="chat-message-actions">
                      <button
                        onClick={() => handleCopyMessage(msg.message_id, msg.content)}
                        className={`chat-action-btn ${copiedMsgId === msg.message_id ? "copied" : ""}`}
                        title="Sao chép nội dung câu trả lời"
                      >
                        {copiedMsgId === msg.message_id ? (
                          <>
                            <CheckIcon size={12} color="#10b981" />
                            <span>Đã sao chép</span>
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

          {/* Loading Indicator */}
          {isLoading && (
            <div className="chat-loading-indicator">
              <span className="chat-spinner" />
              <span>Đang đối chiếu tài liệu và tính toán...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Prompt Input Box (ChatGPT / Claude Style) */}
      <div className="chat-input-wrapper">
        <div className="chat-input-column">
          {/* Quick suggestions when input is empty */}
          {messages.length <= 3 && (
            <div className="chat-sample-prompts">
              {samplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(p)}
                  disabled={isLoading || !hasSources}
                  className="chat-sample-btn"
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
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                hasSources
                  ? "Đặt câu hỏi về BCTC (ví dụ: So sánh doanh thu và tính tốc độ tăng trưởng)..."
                  : "Hãy chọn tài liệu nguồn ở thanh phía trên trước khi đặt câu hỏi"
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
