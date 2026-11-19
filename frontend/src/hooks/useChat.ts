import { useRef, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { ApiError, errorText, signInHelps } from "../services/api";
import { chatService } from "../services/chat";
import { AskMode, ChatMessage, ChatStage, ClickKind } from "../types/chat";
import { doneAnswering, hasOlderPage, loadedMessages, MESSAGE_PAGE, messagesOf, moveStage, MessagesByChat, olderMessages, pageCursor, putMessages, startAnswering, StageByChat } from "./chatStore";
import { ShowToast } from "./useToast";

interface ChatOptions {
  notebookId: string;
  selectedDocIds: string[];
  maxSources: number;
  showToast: ShowToast;
  onLoginRequired: () => void;
  onTitle: (notebookId: string, title: string) => void;
}

/**
 * Tin nhắn của đoạn chat đang mở (mỗi notebook là một đoạn chat) và gửi câu hỏi (khách chỉ được 1 tài liệu nguồn).
 * Mỗi đoạn chat giữ danh sách tin nhắn và dấu "đang trả lời" riêng: câu trả lời đang được viết thuộc về đoạn chat nơi câu hỏi được gửi,
 * dù người dùng đã mở đoạn chat khác (chatStore.ts).
 */
export function useChat({ notebookId, selectedDocIds, maxSources, showToast, onLoginRequired, onTitle }: ChatOptions) {
  const [byChat, setByChat] = useState<MessagesByChat>({});
  const [answering, setAnswering] = useState<StageByChat>({});
  const answeringRef = useRef<StageByChat>({});  // the same marks, readable at once inside a callback (the state only after the next render)
  const { t, lang } = useLanguage();

  const messages = messagesOf(byChat, notebookId);
  const isLoading = notebookId in answering;
  const stage = answering[notebookId] ?? null;

  const markAnswering = (update: (marks: StageByChat) => StageByChat) => {
    answeringRef.current = update(answeringRef.current);
    setAnswering(answeringRef.current);
  };
  const putIn = (chatId: string, update: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => setByChat((all) => putMessages(all, chatId, update));

  /** The messages the server has for a chat that was just opened: its newest page (D7: a long chat is read MESSAGE_PAGE messages at a time). */
  const showMessages = (chatId: string, fromServer: ChatMessage[]) => {
    const marks = answeringRef.current;
    setByChat((all) => loadedMessages(all, chatId, fromServer, marks));
    setOlderIn((o) => ({ ...o, [chatId]: hasOlderPage(fromServer, MESSAGE_PAGE) }));
  };

  // "Show earlier messages": the page before the oldest message shown
  const [olderIn, setOlderIn] = useState<Record<string, boolean>>({});
  const [loadingOlder, setLoadingOlder] = useState(false);
  const hasOlder = !!olderIn[notebookId];
  const loadOlder = async () => {
    const chatId = notebookId;
    const before = pageCursor(messages);
    if (before === null || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const page = await chatService.getMessages(chatId, { limit: MESSAGE_PAGE, before });
      setByChat((all) => olderMessages(all, chatId, page));
      setOlderIn((o) => ({ ...o, [chatId]: hasOlderPage(page, MESSAGE_PAGE) }));
    } catch {
      showToast(t.workspace.connectionFailed, "error");
    } finally {
      setLoadingOlder(false);
    }
  };

  const loginWarning = (detail: string) => showToast(detail, "warning", t.toasts.signInNow, onLoginRequired);

  const sendMessage = async (queryText: string, mentions?: string[], retryOf?: string, mode?: AskMode) => {
    if (selectedDocIds.length === 0) {
      showToast(t.toasts.selectFiling, "warning");
      return;
    }
    // The chat this question belongs to: everything below is written there, whichever chat is open when the answer comes
    const chatId = notebookId;
    const put = (update: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => putIn(chatId, update);
    const assistantNote = (id: string, content: string): ChatMessage => ({
      message_id: `${id}_${Date.now()}`,
      notebook_id: chatId,
      role: "assistant",
      content,
      created_at: new Date().toISOString(),
    });
    // a question asked again by a button is marked as such (on the question, while waiting, on its answer, on the answer clicked)
    const click: ClickKind | undefined = retryOf ? mode ?? "chooser" : undefined;
    const clickMark = click ? { click } : {};
    put((prev) => [
      // one click only: the answer searched again loses its "search again" buttons (the server refuses a second click too)
      ...(retryOf
        ? prev.map((m) =>
            m.message_id === retryOf
              ? { ...m, clicked: click, alternatives: (m.alternatives || []).filter((a) => !a.kind), actions: m.actions && { ...m.actions, chooser: [], search_more: null, try_again: false, search_all: false } }
              : m
          )
        : prev),
      {
        message_id: `msg_user_${Date.now()}`,
        notebook_id: chatId,
        role: "user",
        content: queryText,
        created_at: new Date().toISOString(),
        ...clickMark,
        ...(click === "chooser" && mentions?.length ? { clickCount: mentions.length } : {}),
      },
    ]);
    markAnswering((marks) => startAnswering(marks, chatId));

    // The answer being written: one message, created by the first piece (or by "understood"), finished by the recorded answer
    const streamId = `msg_asst_${Date.now()}`;
    const upsert = (patch: Partial<ChatMessage>) =>
      put((prev) =>
        prev.some((m) => m.message_id === streamId)
          ? prev.map((m) => (m.message_id === streamId ? { ...m, ...patch } : m))
          : [...prev, { message_id: streamId, notebook_id: chatId, role: "assistant", content: "", created_at: new Date().toISOString(), streaming: true, ...clickMark, ...patch }]
      );
    let pending = "";  // pieces not drawn yet: drawn once per frame, not once per piece
    let frame = 0;
    const draw = () => {
      frame = 0;
      const text = pending;
      pending = "";
      put((prev) =>
        prev.some((m) => m.message_id === streamId)
          ? prev.map((m) => (m.message_id === streamId ? { ...m, content: m.content + text } : m))
          : [...prev, { message_id: streamId, notebook_id: chatId, role: "assistant", content: text, created_at: new Date().toISOString(), streaming: true, ...clickMark }]
      );
    };

    try {
      const data = await chatService.queryStream(
        {
          notebook_id: chatId,
          query: queryText,
          document_ids: Array.from(new Set([...(mentions || []), ...selectedDocIds])).slice(0, maxSources),
          mentions,
          ui_lang: lang,
          ...(retryOf ? { retry_of: retryOf } : {}),
          ...(retryOf && mode ? { [mode]: true } : {}),
        },
        {
          onStage: (s: ChatStage) => markAnswering((marks) => moveStage(marks, chatId, s)),
          onUnderstood: (understood, alternatives) => upsert({ understood, alternatives: alternatives || [] }),
          onDelta: (text) => {
            pending += text;
            if (!frame) frame = requestAnimationFrame(draw);
          },
          onRetract: () => {  // the server's checks stopped the answer: nothing it wrote stays on screen
            if (frame) cancelAnimationFrame(frame);
            frame = 0;
            pending = "";
            upsert({ content: "" });
          },
        }
      );
      if (frame) cancelAnimationFrame(frame);
      pending = "";
      upsert({
        content: data.answer,  // the checked answer replaces what was streamed
        citations: data.citations || [],
        understood: data.understood || "",
        alternatives: data.alternatives || [],
        actions: data.actions,
        query: queryText,
        streaming: false,
        ...(data.message_id ? { message_id: data.message_id, user_rating: null } : {}),  // the stored answer: it can be reported
      });
      onTitle(chatId, data.title);
    } catch (err) {
      if (frame) cancelAnimationFrame(frame);
      pending = "";
      put((prev) => prev.filter((m) => m.message_id !== streamId));  // a half-written answer is not left behind
      if (err instanceof ApiError) {
        const detail = err.status >= 500 ? t.workspace.systemBusy : errorText(err, t, t.workspace.systemBusy);  // lỗi hệ thống không lộ chi tiết cho người dùng
        // Signing in helps on 401 or for the refusals that name it (a 403 alone does not: a read-only notebook stays read-only)
        if (signInHelps(err)) {
          loginWarning(detail);
        } else {
          showToast(detail, "error");
        }
        put((prev) => [...prev, assistantNote("msg_err", `⚠️ ${detail}`)]);
      } else {
        showToast(t.workspace.connectionFailed, "error");
        put((prev) => [...prev, assistantNote("msg_err", `⚠️ ${t.workspace.connectionFailed}`)]);
      }
    } finally {
      markAnswering((marks) => doneAnswering(marks, chatId));
    }
  };

  /** Shown at once; put back if the server refuses. */
  const flagAnswer = async (messageId: string, flagged: boolean) => {
    const chatId = notebookId;
    const rate = (rating: number | null) =>
      putIn(chatId, (prev) => prev.map((m) => (m.message_id === messageId ? { ...m, user_rating: rating } : m)));
    rate(flagged ? -1 : null);
    try {
      await chatService.flag(chatId, messageId, flagged);
      if (flagged) showToast(t.workspace.reportSent, "success");
    } catch (err) {
      rate(flagged ? null : -1);
      showToast(err instanceof ApiError && err.status < 500 ? errorText(err, t, t.workspace.systemBusy) : t.workspace.systemBusy, "error");
    }
  };

  return { messages, showMessages, isLoading, stage, sendMessage, flagAnswer, hasOlder, loadingOlder, loadOlder };
}
