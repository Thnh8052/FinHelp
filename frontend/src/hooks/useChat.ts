import { useRef, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { ApiError, errorText, signInHelps } from "../services/api";
import { chatService } from "../services/chat";
import { ChatMessage, ChatStage } from "../types/chat";
import { ShowToast } from "./useToast";

interface ChatOptions {
  notebookId: string;
  selectedDocIds: string[];
  maxSources: number;
  showToast: ShowToast;
  onLoginRequired: () => void;
  onTitle: (notebookId: string, title: string) => void;
}

/** Tin nhắn của đoạn chat đang mở (mỗi notebook là một đoạn chat) và gửi câu hỏi (khách chỉ được 1 tài liệu nguồn). */
export function useChat({ notebookId, selectedDocIds, maxSources, showToast, onLoginRequired, onTitle }: ChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [stage, setStage] = useState<ChatStage | null>(null);
  const pending = useRef("");  // pieces not drawn yet: drawn once per frame, not once per piece
  const { t } = useLanguage();

  const loginWarning = (detail: string) => showToast(detail, "warning", t.toasts.signInNow, onLoginRequired);

  const sendMessage = async (queryText: string, mentions?: string[]) => {
    if (selectedDocIds.length === 0) {
      showToast(t.toasts.selectFiling, "warning");
      return;
    }
    const assistantNote = (id: string, content: string): ChatMessage => ({
      message_id: `${id}_${Date.now()}`,
      notebook_id: notebookId,
      role: "assistant",
      content,
      created_at: new Date().toISOString(),
    });
    setMessages((prev) => [
      ...prev,
      {
        message_id: `msg_user_${Date.now()}`,
        notebook_id: notebookId,
        role: "user",
        content: queryText,
        created_at: new Date().toISOString(),
      },
    ]);
    setIsLoading(true);
    setStage("understanding");

    // The answer being written: one message, created by the first piece (or by "understood"), finished by the recorded answer
    const streamId = `msg_asst_${Date.now()}`;
    const upsert = (patch: Partial<ChatMessage>) =>
      setMessages((prev) =>
        prev.some((m) => m.message_id === streamId)
          ? prev.map((m) => (m.message_id === streamId ? { ...m, ...patch } : m))
          : [...prev, { message_id: streamId, notebook_id: notebookId, role: "assistant", content: "", created_at: new Date().toISOString(), streaming: true, ...patch }]
      );
    let frame = 0;
    const draw = () => {
      frame = 0;
      const text = pending.current;
      pending.current = "";
      setMessages((prev) =>
        prev.some((m) => m.message_id === streamId)
          ? prev.map((m) => (m.message_id === streamId ? { ...m, content: m.content + text } : m))
          : [...prev, { message_id: streamId, notebook_id: notebookId, role: "assistant", content: text, created_at: new Date().toISOString(), streaming: true }]
      );
    };
    pending.current = "";

    try {
      const data = await chatService.queryStream(
        {
          notebook_id: notebookId,
          query: queryText,
          document_ids: Array.from(new Set([...(mentions || []), ...selectedDocIds])).slice(0, maxSources),
          mentions,
        },
        {
          onStage: setStage,
          onUnderstood: (understood, alternatives) => upsert({ understood, alternatives: alternatives || [] }),
          onDelta: (text) => {
            pending.current += text;
            if (!frame) frame = requestAnimationFrame(draw);
          },
        }
      );
      if (frame) cancelAnimationFrame(frame);
      pending.current = "";
      upsert({
        content: data.answer,  // the checked answer replaces what was streamed
        citations: data.citations || [],
        understood: data.understood || "",
        alternatives: data.alternatives || [],
        query: queryText,
        streaming: false,
        ...(data.message_id ? { message_id: data.message_id, user_rating: null } : {}),  // the stored answer: it can be reported
      });
      onTitle(notebookId, data.title);
    } catch (err) {
      if (frame) cancelAnimationFrame(frame);
      pending.current = "";
      setMessages((prev) => prev.filter((m) => m.message_id !== streamId));  // a half-written answer is not left behind
      if (err instanceof ApiError) {
        const detail = err.status >= 500 ? t.workspace.systemBusy : errorText(err, t, t.workspace.systemBusy);  // lỗi hệ thống không lộ chi tiết cho người dùng
        // Signing in helps on 401 or for the refusals that name it (a 403 alone does not: a read-only notebook stays read-only)
        if (signInHelps(err)) {
          loginWarning(detail);
        } else {
          showToast(detail, "error");
        }
        setMessages((prev) => [...prev, assistantNote("msg_err", `⚠️ ${detail}`)]);
      } else {
        showToast(t.workspace.connectionFailed, "error");
        setMessages((prev) => [...prev, assistantNote("msg_err", `⚠️ ${t.workspace.connectionFailed}`)]);
      }
    } finally {
      setIsLoading(false);
      setStage(null);
    }
  };

  /** Shown at once; put back if the server refuses. */
  const flagAnswer = async (messageId: string, flagged: boolean) => {
    const rate = (rating: number | null) =>
      setMessages((prev) => prev.map((m) => (m.message_id === messageId ? { ...m, user_rating: rating } : m)));
    rate(flagged ? -1 : null);
    try {
      await chatService.flag(notebookId, messageId, flagged);
      if (flagged) showToast(t.workspace.reportSent, "success");
    } catch (err) {
      rate(flagged ? null : -1);
      showToast(err instanceof ApiError && err.status < 500 ? errorText(err, t, t.workspace.systemBusy) : t.workspace.systemBusy, "error");
    }
  };

  return { messages, setMessages, isLoading, stage, sendMessage, flagAnswer };
}
