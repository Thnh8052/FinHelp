import React, { useState, useRef, useEffect, useLayoutEffect } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { AskMode, ChatMessage, ChatStage, CitationItem, MentionOption } from "../../types/chat";
import { SourceCard } from "./SourceCard";
import { AnswerActions, SourceChooser } from "./AnswerActions";
import { displayNumbers, renumber } from "../../utils/citationNumbers";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { barIndex, STAGES, waitingText } from "./waiting";
import { citedFigures } from "../notebook/locateExcerpt";
import { pinnedAfterScroll, scrollAfterChange, ScrollSnapshot, snapshotOf } from "./scrollPolicy";
import { ArrowUp, ChevronDown, Flag, Plus, Sparkles } from "lucide-react";
import { CheckIcon, ChevronLeftIcon, ChevronRightIcon, CopyIcon, FileTextIcon } from "../common/Icons";
import "./chat.css";

interface ChatContainerProps {
  messages: ChatMessage[];
  onSendMessage: (query: string, mentions?: string[], retryOf?: string, mode?: AskMode) => void;
  /** Report (or withdraw) wrong figures in a stored answer. */
  onFlagAnswer?: (messageId: string, flagged: boolean) => void;
  isLoading: boolean;
  /** What the system is doing for the question being answered (streamed chat). */
  loadingStage?: ChatStage | null;
  onSelectCitation: (citation: CitationItem) => void;
  onToggleSources?: () => void;
  isSourcesOpen?: boolean;
  /** File name of each report in this chat, by document_id: the source cards under an answer show it. */
  documentNames?: Record<string, string>;
  /** Which chat this is (the notebook id): the question box keeps one unsent draft per chat. */
  chatKey?: string;
  /** What a chat with no question yet shows. It is given the way to put an example question into the question box. */
  startScreen: (pickQuestion: (question: string) => void) => React.ReactNode;
  /** Chưa chọn tài liệu nguồn: không cho gửi (hệ thống không tự đoán phạm vi). */
  hasSources?: boolean;
  /** Đang tải lên hoặc đang xử lý bóc tách/lập chỉ mục các file PDF. */
  isProcessing?: boolean;
  /** Tài liệu nguồn đã chọn, để tag bằng @ (câu hỏi chỉ về các tài liệu được tag). */
  mentionOptions?: MentionOption[];
  /** D7: a long chat shows its newest page; older messages come with "show earlier messages". */
  hasOlder?: boolean;
  isLoadingOlder?: boolean;
  onLoadOlder?: () => void;
}

/** The longest question the server takes (MAX_QUESTION_CHARS in backend query_router/input_policy.py); a longer one is refused after it was sent. */
const MAX_QUESTION_CHARS = 5000;

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  onSendMessage,
  onFlagAnswer,
  isLoading,
  loadingStage,
  onSelectCitation,
  onToggleSources,
  isSourcesOpen = false,
  documentNames = {},
  chatKey = "",
  startScreen,
  hasSources = true,
  isProcessing = false,
  mentionOptions = [],
  hasOlder = false,
  isLoadingOlder = false,
  onLoadOlder,
}) => {
  const { t } = useLanguage();
  const [input, setInput] = useState("");
  const [mentions, setMentions] = useState<string[]>([]);
  // Unsent text per chat: leaving a chat stores what was typed, entering one shows its own draft (or an empty box). Tags (@) belong to the chat they were made in.
  const drafts = useRef(new Map<string, string>());
  const shownChat = useRef(chatKey);
  useEffect(() => {
    if (shownChat.current === chatKey) return;
    const left = shownChat.current;
    shownChat.current = chatKey;
    if (!left) return; // no chat was open yet (the list was still loading): what was typed is kept
    drafts.current.set(left, input);
    setInput(drafts.current.get(chatKey) ?? "");
    setMentions([]);
  }, [chatKey]); // eslint-disable-line react-hooks/exhaustive-deps -- reads the text at the moment of the switch
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // The real stage of the answer; a stage that lasts long says so, so the user knows nothing hung
  const stageName = loadingStage ?? "understanding";
  const stageIndex = barIndex(stageName);
  const [isSlow, setIsSlow] = useState(false);
  // "analyzing" (the model's first reasoning piece arrived): the seconds are counted from there
  const [analyzingSeconds, setAnalyzingSeconds] = useState(0);
  useEffect(() => {
    setAnalyzingSeconds(0);
    if (!isLoading || stageName !== "analyzing") return;
    const since = Date.now();
    const timer = setInterval(() => setAnalyzingSeconds(Math.floor((Date.now() - since) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [isLoading, stageName]);
  useEffect(() => {
    setIsSlow(false);
    if (!isLoading) return;
    const timer = setTimeout(() => setIsSlow(true), 20000);
    return () => clearTimeout(timer);
  }, [isLoading, stageName]);
  // Once the answer shows up the waiting line goes away, unless the system checks it again (the text may then be replaced)
  const isWriting = messages.some((m) => m.streaming && m.content);
  const showWaiting = isLoading && (!isWriting || stageName === "checking");
  // The answer's card may already be on screen (the note "I understood the question as…" arrives first) while it has no text yet: the waiting block then goes inside it
  const lastMessage = messages[messages.length - 1];
  const waitingInMessage = showWaiting && lastMessage?.role === "assistant" && !!lastMessage.streaming && !lastMessage.content;
  // a button asked the question again: the wait says what is being done instead of the plain stages
  const lastQuestion = [...messages].reverse().find((m) => m.role === "user");
  const waitingClick = isLoading && lastQuestion?.click ? lastQuestion.click : "";

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
  const streamRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true); // the list is scrolled to its end: it stays there when the box under it grows
  const lastTopRef = useRef(0); // where the list was at the last scroll event: only a move up unpins
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
    // only the message list scrolls: scrollIntoView also scrolled the outer chat box (overflow hidden is still scrollable by code), which hid the header
    const stream = streamRef.current;
    stream?.scrollTo({ top: stream.scrollHeight, behavior: "smooth" });
  };

  // The list moves only when a chat opens or a question is asked; a flag on an old answer or the text being written leaves a reader who scrolled up where they are (scrollPolicy.ts)
  const lastSnapshot = useRef<ScrollSnapshot | null>(null);
  useEffect(() => {
    const next = snapshotOf(chatKey, messages);
    const step = scrollAfterChange(lastSnapshot.current, next, pinnedRef.current);
    lastSnapshot.current = next;
    pinnedRef.current = step.pinned;
    if (step.to === "top") streamRef.current?.scrollTo({ top: 0 });
    else if (step.to === "bottom") scrollToBottom();
  }, [messages, chatKey]);

  // Older messages put above: the reader keeps seeing what was on screen (the list grows upwards by the height they add)
  const olderAnchor = useRef<{ height: number; top: number } | null>(null);
  const loadOlderHere = () => {
    const s = streamRef.current;
    if (s) olderAnchor.current = { height: s.scrollHeight, top: s.scrollTop };
    onLoadOlder?.();
  };
  useLayoutEffect(() => {
    const s = streamRef.current;
    if (!olderAnchor.current || !s || s.scrollHeight === olderAnchor.current.height) return;
    s.scrollTop = s.scrollHeight - olderAnchor.current.height + olderAnchor.current.top;
    olderAnchor.current = null;
  }, [messages]);
  useEffect(() => {
    olderAnchor.current = null;  // another chat: nothing to keep
  }, [chatKey]);

  // A growing question box (or a panel opening) shrinks the list: if it was at its end it stays at its end, so the last lines are not pushed out of view
  useEffect(() => {
    const stream = streamRef.current;
    if (!stream) return;
    const observer = new ResizeObserver(() => {
      if (pinnedRef.current) stream.scrollTop = stream.scrollHeight;
    });
    observer.observe(stream);
    return () => observer.disconnect();
  }, []);

  // The question box grows with its text up to the CSS max-height (min-height and max-height live in chat.css), then scrolls
  const autoResizeTextarea = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = parseFloat(getComputedStyle(el).maxHeight) || 180;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
    el.style.overflowY = el.scrollHeight > max ? "auto" : "hidden";
  };

  useEffect(() => {
    autoResizeTextarea();
  }, [input]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    let width = el.clientWidth;
    const observer = new ResizeObserver(() => {
      if (el.clientWidth === width) return; // only a change of width wraps the text differently; a change of height is our own
      width = el.clientWidth;
      autoResizeTextarea();
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isLoading || !hasSources || isProcessing) return;
    const toSend = input;
    const usedMentions = mentions.length > 0 ? mentions : undefined;
    setInput(""); // the box shrinks back by itself (the effect on input)
    setMentions([]);
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

  // What the system is doing now, a placeholder for the text to come, and how far along it is (4 steps: understand, search, write, check)
  const waitingBlock = (
    <div className="chat-loading-card">
      <p className="chat-loading-status" role="status">
        <span className="chat-spinner" aria-hidden />
        {waitingText({ stage: stageName, slow: isSlow, click: waitingClick, seconds: analyzingSeconds, texts: { stages: t.workspace.loadingStages, slow: t.workspace.loadingSlow, click: t.workspace.clickStage } })}
      </p>
      <div className="chat-skeleton" aria-hidden>
        <i /><i /><i />
      </div>
      <div className="chat-stage-bar" aria-hidden>
        {STAGES.map((s, i) => (
          <span key={s} className={i < stageIndex ? "done" : i === stageIndex ? "current" : ""} />
        ))}
      </div>
    </div>
  );

  // A chat with no question yet shows the start screen instead of the scope bar and the suggestions
  const showStart = messages.length === 0 && !isLoading;
  // An example question goes into the question box; the box takes it even while it is still locked (no report yet), and it is asked once a report is ready
  const pickQuestion = (question: string) => {
    setInput(question);
    textareaRef.current?.focus();
  };

  // "2 reports selected" in the scope bar, "2 reports in scope" in the composer; with none chosen both say so / invite to choose
  const reportCount = mentionOptions.length;
  const scopeText =
    reportCount === 0
      ? t.workspace.noFilingsSelected
      : (reportCount === 1 ? t.workspace.reportsSelectedOne : t.workspace.reportsSelectedMany).replace("{n}", String(reportCount));
  const scopeChipText =
    reportCount === 0
      ? t.workspace.chooseFilingsBtn
      : (reportCount === 1 ? t.workspace.scopeChipOne : t.workspace.scopeChipMany).replace("{n}", String(reportCount));

  return (
    <div className="chat-container">
      {/* Scope bar: how many reports the questions are asked about, which ones, and the way to change them. The start screen says it itself. */}
      {!showStart && <div className="chat-header">
        <div className="chat-header-sources">
          <FileTextIcon size={16} color="var(--accent-text)" />
          <span className="chat-sources-label">{scopeText}</span>
          <div className="chat-sources-tags">
            {/* Two tags at most, each shortened with "…" (full name on hover); the rest as "+N": a scrolling strip cut the second name in half */}
            {mentionOptions.slice(0, 2).map((opt) => (
              <span key={opt.document_id} className="chat-source-tag" title={opt.label}>
                {opt.label}
              </span>
            ))}
            {mentionOptions.length > 2 && (
              <span className="chat-source-tag" title={mentionOptions.slice(2).map((o) => o.label).join("\n")}>
                +{mentionOptions.length - 2}
              </span>
            )}
          </div>
        </div>
        {onToggleSources && (
          <button
            type="button"
            onClick={onToggleSources}
            className={`chat-manage-sources-btn ${isSourcesOpen ? "active" : ""}`}
            aria-expanded={isSourcesOpen}
          >
            <span>{isSourcesOpen ? t.nav.closeSources : t.nav.manageSources}</span>
            <ChevronDown size={15} aria-hidden />
          </button>
        )}
      </div>}

      {/* Messages Stream */}
      <div
        className="chat-messages-stream"
        ref={streamRef}
        onScroll={(e) => {
          const s = e.currentTarget;
          pinnedRef.current = pinnedAfterScroll(pinnedRef.current, { gap: s.scrollHeight - s.clientHeight - s.scrollTop, top: s.scrollTop, lastTop: lastTopRef.current });
          lastTopRef.current = s.scrollTop;
        }}
      >
        {showStart && startScreen(pickQuestion)}
        <div className="chat-messages-column">
          {hasOlder && onLoadOlder && (
            <button type="button" className="chat-load-older" onClick={loadOlderHere} disabled={isLoadingOlder}>
              {isLoadingOlder ? t.workspace.loadingOlder : t.workspace.loadOlder}
            </button>
          )}
          {messages.map((msg, index) => {
            const isUser = msg.role === "user";
            // Only the excerpts the answer uses, each keeping its own [n]
            const used = (msg.citations || [])
              .map((cite, idx) => ({ cite, index: idx + 1 }))
              .filter(({ cite }) => cite.cited !== false);
            // Shown as 1, 2, 3 in the order the text meets them; the excerpt behind each number keeps its own (utils/citationNumbers)
            const numbering = displayNumbers(msg.content, used.map((u) => u.index));
            const shownUsed = [...used].sort((a, b) => (numbering.get(a.index) ?? 0) - (numbering.get(b.index) ?? 0));

            return (
              <div
                key={msg.message_id}
                className={`chat-message-row ${isUser ? "user" : "assistant"}`}
              >
                {/* The question is labelled; an answer carries its own header inside its card */}
                {isUser && <span className="chat-sender-label">{t.workspace.youLabel}</span>}

                {/* Message Box */}
                <div className={`chat-message-bubble ${isUser ? "user" : "assistant"}`}>
                  {!isUser && (
                    <div className="chat-answer-head">
                      <span className="chat-answer-avatar" aria-hidden>
                        <Sparkles size={16} />
                      </span>
                      <span className="chat-answer-name">{t.workspace.aiLabel}</span>
                      {!msg.streaming && used.length > 0 && (
                        <span className="chat-answer-badge">
                          <CheckIcon size={14} />
                          {(used.length === 1 ? t.workspace.sourceRefsOne : t.workspace.sourceRefsMany).replace("{n}", String(used.length))}
                        </span>
                      )}
                    </div>
                  )}
                  {(() => {
                    // which button asked this question / answer again (a reloaded question takes it from its answer)
                    const click = isUser ? msg.click || messages[index + 1]?.click : msg.click;
                    if (!click) return null;
                    const label = isUser
                      ? click === "chooser" && msg.clickCount ? t.workspace.clickAskN.replace("{n}", String(msg.clickCount)) : t.workspace.clickAsk[click]
                      : t.workspace.clickResult[click];
                    return <div className={`chat-click-mark ${isUser ? "on-question" : "on-answer"}`}>↻ {label}</div>;
                  })()}
                  {!isUser && msg.understood && <div className="chat-understood">{msg.understood}</div>}
                  {!isUser && msg.actions?.chooser_first && !!msg.actions.chooser?.length && (msg.query || messages[index - 1]?.role === "user") && (
                    <SourceChooser
                      chooser={msg.actions.chooser}
                      disabled={isLoading}
                      startOpen
                      onAsk={(sources) => onSendMessage(msg.query || messages[index - 1].content, sources, msg.message_id)}
                    />
                  )}
                  {isUser ? (
                    <div className="chat-message-text">{msg.content}</div>
                  ) : (
                    <MarkdownRenderer
                      content={msg.content}
                      citations={msg.citations}
                      onSelectCitation={onSelectCitation}
                      numbering={numbering}
                    />
                  )}
                  {!isUser && waitingInMessage && index === messages.length - 1 && waitingBlock}
                  {!isUser && msg.alternatives && msg.alternatives.length > 0 && msg.query && (
                    <div className="chat-alternatives">
                      {msg.alternatives.map((a) => (
                        <button
                          key={a.document_id}
                          type="button"
                          className="chat-sample-btn"
                          disabled={isLoading}
                          onClick={() => onSendMessage(msg.query!, a.document_ids?.length ? a.document_ids : [a.document_id], a.kind ? msg.message_id : undefined)}
                        >
                          {a.kind === "retry_all" ? t.workspace.retryAll
                            : (a.kind === "retry_one" ? t.workspace.retryIn : t.workspace.queryWith).replace("{label}", a.label)}
                        </button>
                      ))}
                    </div>
                  )}
                  {/* Where the answer comes from: one card per excerpt it uses, each keeping its own [n] */}
                  {!isUser && !msg.streaming && used.length > 0 && (
                    <div className="chat-citations-container">
                      <span className="chat-citations-title">{t.workspace.sourceCitationsTitle}</span>
                      <div className="chat-citations-list">
                        {shownUsed.map(({ cite, index }) => (
                          <SourceCard
                            key={cite.citation_id}
                            citation={cite}
                            index={numbering.get(index) ?? index}
                            fileName={documentNames[cite.document_id]}
                            onClick={() => onSelectCitation({ ...cite, figures: citedFigures(msg.content, index) })}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Under the card: the answer buttons on the left, copy / report beside them */}
                {!isUser && !msg.streaming && (
                    <div className="chat-message-footer">
                      {msg.clicked && <div className="chat-clicked-note" role="note">{t.workspace.clickedNote[msg.clicked]}</div>}
                      <div className="chat-message-toolbar">
                        {msg.actions && (msg.query || messages[index - 1]?.role === "user") && (
                          <AnswerActions
                            actions={msg.actions}
                            disabled={isLoading}
                            onAsk={(sources, mode) => onSendMessage(msg.query || messages[index - 1].content, sources, msg.message_id, mode)}
                            onEdit={() => {
                              setInput(msg.query || messages[index - 1].content);
                              textareaRef.current?.focus();
                            }}
                          />
                        )}
                        <div className="chat-message-actions">
                          <button
                            type="button"
                            onClick={() => handleCopy(renumber(msg.content, numbering), msg.message_id)}
                            className={`chat-action-btn chat-copy-btn ${copiedMsgId === msg.message_id ? "copied" : ""}`}
                            title={t.workspace.copyAnswer}
                          >
                            {copiedMsgId === msg.message_id ? (
                              <>
                                <CheckIcon size={12} color="var(--positive)" />
                                <span className="chat-copied-text">{t.common.copied}</span>
                              </>
                            ) : (
                              <>
                                <CopyIcon size={12} />
                                <span>{t.workspace.copyAnswer}</span>
                              </>
                            )}
                          </button>
                          {/* only an answer with sources has figures to report (not a refusal, a greeting or a fixed reply) */}
                          {onFlagAnswer && msg.user_rating !== undefined && (msg.citations?.length ?? 0) > 0 && (
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
                      </div>
                    </div>
                )}
              </div>
            );
          })}

          {/* Nothing of the answer is on screen yet: its card appears with the waiting block in it */}
          {showWaiting && !waitingInMessage && (
            <div className="chat-message-row assistant">
              <div className="chat-message-bubble assistant" aria-busy="true">
                <div className="chat-answer-head">
                  <span className="chat-answer-avatar" aria-hidden>
                    <Sparkles size={16} />
                  </span>
                  <span className="chat-answer-name">{t.workspace.aiLabel}</span>
                </div>
                {waitingBlock}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Floating Prompt Input Box */}
      <div className="chat-input-wrapper">
        <div className="chat-input-column">
          {/* Quick suggestions when input is empty */}
          {!showStart && messages.length <= 3 && (
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

          {/* Composer: the question on top, the reports it is asked about underneath */}
          <form onSubmit={handleSubmit} className={`chat-input-form ${isProcessing ? "is-processing" : ""}`}>
            <div className="chat-input-row">
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
                maxLength={MAX_QUESTION_CHARS}
                className="chat-input-textarea"
              />

              <button
                type="submit"
                disabled={!canSubmit}
                aria-label={t.workspace.sendBtn}
                className={`chat-send-btn ${canSubmit ? "active" : "inactive"}`}
              >
                <ArrowUp size={20} aria-hidden />
              </button>
            </div>
            {onToggleSources ? (
              <button type="button" className="chat-scope-chip" onClick={onToggleSources} aria-expanded={isSourcesOpen}>
                <Plus size={16} aria-hidden />
                {scopeChipText}
              </button>
            ) : (
              <span className="chat-scope-chip">{scopeChipText}</span>
            )}
          </form>

          <div className="chat-input-hint">
            <span>{t.workspace.inputShortcuts}</span>
            {/* the box stops at the limit: a long paste is cut, so the count shows up before that happens */}
            {input.length >= MAX_QUESTION_CHARS * 0.9 && <span role="status">{input.length} / {MAX_QUESTION_CHARS}</span>}
            <span>{t.workspace.checkFigures}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
