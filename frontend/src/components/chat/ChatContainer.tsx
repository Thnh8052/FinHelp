import React, { useState, useRef, useEffect } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { ChatMessage, ChatStage, CitationItem, MentionOption } from "../../types/chat";
import { CitationBadge } from "./CitationBadge";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { citedFigures } from "../notebook/locateExcerpt";
import { Flag } from "lucide-react";
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, CopyIcon, FileTextIcon, SendIcon } from "../common/Icons";
import "./chat.css";

interface ChatContainerProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, mentions?: string[]) => void;
  /** Report (or withdraw) wrong figures in a stored answer. */
  onFlagAnswer?: (messageId: string, flagged: boolean) => void;
  isLoading: boolean;
  /** What the system is doing for the question being answered (streamed chat). */
  loadingStage?: ChatStage | null;
  onSelectCitation: (citation: CitationItem) => void;
  onClearChat?: () => void;
  sessionTitle?: string;
  onNewChat?: () => void;
  onOpenSources?: () => void;
  onToggleSources?: () => void;
  isSourcesOpen?: boolean;
  /** Chưa chọn tài liệu nguồn: không cho gửi (hệ thống không tự đoán phạm vi). */
  hasSources?: boolean;
  /** Đang tải lên hoặc đang xử lý bóc tách/lập chỉ mục các file PDF. */
  isProcessing?: boolean;
  /** Tài liệu nguồn đã chọn, để tag bằng @ (câu hỏi chỉ về các tài liệu được tag). */
  mentionOptions?: MentionOption[];
}

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  onSendMessage,
  onFlagAnswer,
  isLoading,
  loadingStage,
  onSelectCitation,
  sessionTitle,
  onNewChat: _onNewChat,
  onOpenSources,
  onToggleSources,
  isSourcesOpen = false,
  hasSources = true,
  isProcessing = false,
  mentionOptions = [],
}) => {
  const { t } = useLanguage();
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // The real stage of the answer; a stage that lasts long says so, so the user knows nothing hung
  const stageName = loadingStage ?? "understanding";
  const [isSlow, setIsSlow] = useState(false);
  useEffect(() => {
    setIsSlow(false);
    if (!isLoading) return;
    const timer = setTimeout(() => setIsSlow(true), 20000);
    return () => clearTimeout(timer);
  }, [isLoading, stageName]);
  // Once the answer shows up the waiting line goes away, unless the system checks it again (the text may then be replaced)
  const isWriting = messages.some((m) => m.streaming && m.content);
  const showWaiting = isLoading && (!isWriting || stageName === "checking");

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
  const promptsTrackRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const dragStartXRef = useRef(0);
  const scrollLeftRef = useRef(0);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScrollBounds = () => {
    const el = promptsTrackRef.current;
    if (!el) return;
    const { scrollLeft, scrollWidth, clientWidth } = el;
    setCanScrollLeft(scrollLeft > 4);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 6);
  };

  const scrollPrompts = (direction: "left" | "right") => {
    const el = promptsTrackRef.current;
    if (!el) return;
    const amount = direction === "left" ? -240 : 240;
    el.scrollBy({ left: amount, behavior: "smooth" });
    setTimeout(checkScrollBounds, 320);
  };

  useEffect(() => {
    checkScrollBounds();
    window.addEventListener("resize", checkScrollBounds);
    return () => window.removeEventListener("resize", checkScrollBounds);
  }, []);

  useEffect(() => {
    const el = promptsTrackRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaY) >= Math.abs(e.deltaX) && e.deltaY !== 0) {
        e.preventDefault();
        el.scrollLeft += e.deltaY * 1.25;
      } else if (e.deltaX !== 0) {
        e.preventDefault();
        el.scrollLeft += e.deltaX * 1.25;
      }
      checkScrollBounds();
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      el.removeEventListener("wheel", onWheel);
    };
  }, []);

  const handlePromptsMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = promptsTrackRef.current;
    if (!el) return;
    isDraggingRef.current = false;
    dragStartXRef.current = e.pageX;
    scrollLeftRef.current = el.scrollLeft;

    const onMouseMove = (moveEvent: MouseEvent) => {
      const walk = (moveEvent.pageX - dragStartXRef.current) * 1.4;
      if (Math.abs(walk) > 4) {
        isDraggingRef.current = true;
      }
      el.scrollLeft = scrollLeftRef.current - walk;
      checkScrollBounds();
    };

    const onMouseUp = () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      setTimeout(() => {
        isDraggingRef.current = false;
      }, 60);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  };

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
    const isSmallMobile = typeof window !== "undefined" && window.innerWidth <= 480;
    const minHeight = isSmallMobile ? 18 : isMobile ? 20 : 22;
    const maxHeight = isMobile ? 120 : 180;
    const newHeight = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight);
    el.style.height = `${newHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  };

  useEffect(() => {
    autoResizeTextarea();
  }, [input]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading || !hasSources || isProcessing) return;
    const toSend = input;
    const usedMentions = mentions.length > 0 ? mentions : undefined;
    setInput("");
    setMentions([]);
    if (textareaRef.current) {
      const isMobile = typeof window !== "undefined" && window.innerWidth <= 768;
      const isSmallMobile = typeof window !== "undefined" && window.innerWidth <= 480;
      textareaRef.current.style.height = isSmallMobile ? "18px" : isMobile ? "20px" : "22px";
      textareaRef.current.style.overflowY = "hidden";
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
    t.workspace.suggestion1,
    t.workspace.suggestion2,
    t.workspace.suggestion3,
  ];

  const canSubmit = !isLoading && hasSources && !isProcessing && !!input.trim();

  return (
    <div className="chat-container">
      {/* Top Header Bar inside Chat Container: Context Bar */}
      <div className="chat-header">
        <div className="chat-header-title-box">
          <span className="chat-header-title">
            {sessionTitle || t.workspace.currentSession}
          </span>
        </div>

        {/* Context bar showing selected documents */}
        <div className="chat-header-sources">
          <span className="chat-sources-label">{t.workspace.activeScope}</span>
          <div className="chat-sources-tags">
            {mentionOptions && mentionOptions.length > 0 ? (
              mentionOptions.map((opt) => (
                <span key={opt.document_id} className="chat-source-tag">
                  {opt.label}
                </span>
              ))
            ) : (
              <span className="chat-source-tag muted">{t.workspace.noFilingsSelected}</span>
            )}
          </div>
          {(onToggleSources || onOpenSources) && (
            <button
              type="button"
              onClick={onToggleSources || onOpenSources}
              className={`chat-manage-sources-btn ${isSourcesOpen ? "active" : ""}`}
              title={isSourcesOpen ? t.nav.closeSources : t.nav.manageSources}
            >
              <span>{isSourcesOpen ? t.nav.closeSources : t.nav.manageSources}</span>
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
                {t.workspace.emptyTitle}
              </div>
              <p className="chat-empty-desc">
                {t.workspace.emptyDesc}
              </p>
              {!hasSources && (onToggleSources || onOpenSources) && (
                <button
                  type="button"
                  onClick={onToggleSources || onOpenSources}
                  className="chat-empty-select-docs-btn"
                >
                  <FileTextIcon size={14} />
                  <span>{t.workspace.chooseFilingsBtn}</span>
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
                  {isUser ? t.workspace.youLabel : t.workspace.aiLabel}
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
                          onClick={() => onSendMessage(msg.query!, a.document_ids?.length ? a.document_ids : [a.document_id])}
                        >
                          {t.workspace.queryWith.replace("{label}", a.label)}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Grounded Evidence Citations: only the excerpts the answer uses, each keeping its own [n] */}
                  {(() => {
                    const used = (msg.citations || [])
                      .map((cite, idx) => ({ cite, index: idx + 1 }))
                      .filter(({ cite }) => cite.cited !== false);
                    if (used.length === 0) return null;
                    return (
                      <div className="chat-citations-container">
                        <div className="chat-citations-title">
                          {t.workspace.sourceCitationsTitle} ({used.length}):
                        </div>
                        <div className="chat-citations-list">
                          {used.map(({ cite, index }) => (
                            <CitationBadge
                              key={cite.citation_id}
                              citation={cite}
                              index={index}
                              onClick={() => onSelectCitation({ ...cite, figures: citedFigures(msg.content, index) })}
                            />
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Actions: Copy */}
                  {!isUser && !msg.streaming && (
                    <div className="chat-message-actions">
                      <button
                        type="button"
                        onClick={() => handleCopy(msg.content, msg.message_id)}
                        className={`chat-action-btn chat-copy-btn ${copiedMsgId === msg.message_id ? "copied" : ""}`}
                        title={t.common.copy}
                      >
                        {copiedMsgId === msg.message_id ? (
                          <>
                            <CheckIcon size={12} color="#10b981" />
                            <span className="chat-copied-text">{t.common.copied}</span>
                          </>
                        ) : (
                          <>
                            <CopyIcon size={12} />
                            <span>{t.common.copy}</span>
                          </>
                        )}
                      </button>
                      {onFlagAnswer && msg.user_rating !== undefined && (
                        <button
                          type="button"
                          onClick={() => onFlagAnswer(msg.message_id, msg.user_rating !== -1)}
                          aria-pressed={msg.user_rating === -1}
                          className={`chat-action-btn chat-flag-btn ${msg.user_rating === -1 ? "flagged" : ""}`}
                          title={t.workspace.reportWrongHint}
                        >
                          <Flag size={12} aria-hidden />
                          <span>{msg.user_rating === -1 ? t.workspace.reportedWrong : t.workspace.reportWrong}</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Assistant Typing / Streaming Skeleton */}
          {showWaiting && (
            <div className="chat-loading-row">
              <span className="chat-sender-label">{t.workspace.aiLabel}</span>
              <div className="chat-loading-bubble">
                <div className="chat-loading-spinner" />
                <span role="status">{isSlow ? t.workspace.loadingSlow : t.workspace.loadingStages[stageName]}</span>
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
              <span className="chat-prompts-label">{t.workspace.suggestionsLabel}</span>

              {canScrollLeft && (
                <button
                  type="button"
                  className="chat-prompts-nav-btn prev"
                  onClick={() => scrollPrompts("left")}
                  aria-label={t.workspace.prevSuggestions}
                  title={t.workspace.scrollLeft}
                >
                  <ChevronLeftIcon size={12} />
                </button>
              )}

              <div
                ref={promptsTrackRef}
                className="chat-sample-track"
                onScroll={checkScrollBounds}
                onMouseDown={handlePromptsMouseDown}
              >
                {samplePrompts.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      if (isDraggingRef.current) return;
                      setInput(p);
                      textareaRef.current?.focus();
                    }}
                    disabled={isLoading || !hasSources || isProcessing}
                    className="chat-sample-btn"
                    title={t.workspace.insertSample}
                  >
                    {p}
                  </button>
                ))}
              </div>

              {canScrollRight && (
                <button
                  type="button"
                  className="chat-prompts-nav-btn next"
                  onClick={() => scrollPrompts("right")}
                  aria-label={t.workspace.moreSuggestions}
                  title={t.workspace.scrollRight}
                >
                  <ChevronRightIcon size={12} />
                </button>
              )}
            </div>
          )}

          {/* Processing Indicator Banner */}
          {isProcessing && (
            <div className="chat-processing-banner">
              <span className="chat-processing-spinner" />
              <span>{t.workspace.processingNotice}</span>
            </div>
          )}

          {/* Tagged documents with @ */}
          {(mentions.length > 0 || mentionMatches.length > 0) && (
            <div className="chat-mentions">
              {mentions.map((id) => (
                <span key={id} className="chat-mention-chip">
                  @{labelOf(id)}
                  <button type="button" aria-label={t.workspace.removeTag} onClick={() => setMentions(mentions.filter((m) => m !== id))}>
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
          <form onSubmit={handleSubmit} className={`chat-input-form ${isProcessing ? "is-processing" : ""}`}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onInput={autoResizeTextarea}
              onKeyDown={handleKeyDown}
              placeholder={
                isProcessing
                  ? t.workspace.placeholderProcessing
                  : hasSources
                  ? t.workspace.placeholderWithDocs
                  : t.workspace.placeholderNoDocs
              }
              disabled={isLoading || !hasSources || isProcessing}
              rows={1}
              className="chat-input-textarea"
            />

            <button
              type="submit"
              disabled={!canSubmit}
              aria-label={t.workspace.sendBtn}
              className={`chat-send-btn ${canSubmit ? "active" : "inactive"}`}
            >
              <SendIcon size={14} />
            </button>
          </form>

          <div className="chat-input-hint">
            {t.workspace.inputShortcuts}
          </div>
        </div>
      </div>
    </div>
  );
};
