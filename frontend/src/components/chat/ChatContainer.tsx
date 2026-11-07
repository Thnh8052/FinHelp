import React, { useState, useRef, useEffect } from "react";
import { ChatMessage, CitationItem, MentionOption } from "../../types/chat";
import { CitationBadge } from "./CitationBadge";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CheckIcon, ChevronRightIcon, CopyIcon, FileTextIcon, SendIcon } from "../common/Icons";
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

  // Auto-expand textarea to match content height (NotebookLM & ChatGPT style)
  const autoResizeTextarea = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const isMobile = typeof window !== "undefined" && window.innerWidth <= 768;
    const minHeight = isMobile ? 24 : 26;
    const maxHeight = isMobile ? 150 : 220;
    const newHeight = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);
    el.style.height = `${newHeight}px`;
  };

  useEffect(() => {
    autoResizeTextarea();
  }, [input]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading || !hasSources) return;
    const toSend = input;
    const usedMentions = mentions.length > 0 ? mentions : undefined;
    setInput("");
    setMentions([]);
    if (textareaRef.current) {
      const isMobile = typeof window !== "undefined" && window.innerWidth <= 768;
      textareaRef.current.style.height = isMobile ? "24px" : "26px";
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
    "Compare Total Revenue across the latest fiscal periods",
    "What is the Operating Margin and YoY expansion?",
    "Analyze Capital Expenditures and Free Cash Flow",
    "Summarize key risk factors and contingent liabilities",
  ];

  const canSubmit = !isLoading && hasSources && !!input.trim();

  return (
    <div className="chat-container">
      {/* Top Header Bar inside Chat Container: Context Bar */}
      <div className="chat-header">
        <div className="chat-header-title-box">
          <span className="chat-header-title">
            {sessionTitle || "Current Session"}
          </span>
        </div>

        {/* Context bar showing selected documents */}
        <div className="chat-header-sources">
          <span className="chat-sources-label">Active Scope:</span>
          <div className="chat-sources-tags">
            {mentionOptions && mentionOptions.length > 0 ? (
              mentionOptions.map((opt) => (
                <span key={opt.document_id} className="chat-source-tag">
                  {opt.label}
                </span>
              ))
            ) : (
              <span className="chat-source-tag muted">No filings selected</span>
            )}
          </div>
          {(onToggleSources || onOpenSources) && (
            <button
              type="button"
              onClick={onToggleSources || onOpenSources}
              className={`chat-manage-sources-btn ${isSourcesOpen ? "active" : ""}`}
              title={isSourcesOpen ? "Close filings drawer" : "Open filings drawer"}
            >
              <span>{isSourcesOpen ? "Close Sources" : "Manage Sources"}</span>
              <ChevronRightIcon size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Messages Stream */}
      <div className="chat-messages-stream">
        <div className="chat-messages-column">
          {messages.length === 0 && !isLoading && (
            <div className="chat-empty-state">
              <div className="chat-empty-title">
                Ready to Analyze Financial Reports
              </div>
              <p className="chat-empty-desc">
                Select or upload financial reports (PDF Form 10-K / Annual Filings), then ask natural language questions about margins, cash flows, or audit disclosures.
              </p>
              {!hasSources && (onToggleSources || onOpenSources) && (
                <button
                  type="button"
                  onClick={onToggleSources || onOpenSources}
                  className="chat-empty-select-docs-btn"
                >
                  <FileTextIcon size={14} />
                  <span>Choose Filings to Analyze</span>
                </button>
              )}
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
                  {isUser ? "You" : "FinHelp"}
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
                          Query with {a.label}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Grounded Evidence Citations */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="chat-citations-container">
                      <div className="chat-citations-title">
                        Source Citations ({msg.citations.length}):
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
                        title="Copy response"
                      >
                        {copiedMsgId === msg.message_id ? (
                          <>
                            <CheckIcon size={12} color="#10b981" />
                            <span className="chat-copied-text">Copied</span>
                          </>
                        ) : (
                          <>
                            <CopyIcon size={12} />
                            <span>Copy</span>
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
              <span className="chat-sender-label">FinHelp</span>
              <div className="chat-loading-bubble">
                <div className="chat-loading-spinner" />
                <span>Retrieving document context and verifying financial metrics...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Floating Prompt Input Box */}
      <div className="chat-input-wrapper">
        <div className="chat-input-column">
          {/* Quick suggestions when input is empty */}
          {messages.length <= 3 && (
            <div className="chat-sample-prompts">
              <span className="chat-prompts-label">Suggestions:</span>
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
                  title="Insert sample query into prompt input"
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Tagged documents with @ */}
          {(mentions.length > 0 || mentionMatches.length > 0) && (
            <div className="chat-mentions">
              {mentions.map((id) => (
                <span key={id} className="chat-mention-chip">
                  @{labelOf(id)}
                  <button type="button" aria-label="Remove tag" onClick={() => setMentions(mentions.filter((m) => m !== id))}>
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
              onInput={autoResizeTextarea}
              onKeyDown={handleKeyDown}
              placeholder={
                hasSources
                  ? "Ask about your financial reports (e.g. Compare revenue growth and calculate CAGR)..."
                  : "Select source filings to begin asking questions..."
              }
              disabled={isLoading || !hasSources}
              rows={1}
              className="chat-input-textarea"
            />

            <button
              type="submit"
              disabled={!canSubmit}
              aria-label="Send"
              className={`chat-send-btn ${canSubmit ? "active" : "inactive"}`}
            >
              <SendIcon size={14} />
            </button>
          </form>

          <div className="chat-input-hint">
            Press Enter to send • Shift + Enter for new line • Type @ to reference a document
          </div>
        </div>
      </div>
    </div>
  );
};
