// Messages and "answering" marks kept per chat, so an answer that is still being written belongs to the chat it was asked in
// even when the reader has opened another one. Pure functions, tested by scripts/test-chat-store.mjs.
import type { ChatMessage, ChatStage } from "../types/chat";

export type MessagesByChat = Record<string, ChatMessage[]>;
/** The chats whose answer is being written, each with its stage. */
export type StageByChat = Record<string, ChatStage>;

const NONE: ChatMessage[] = [];

export const messagesOf = (all: MessagesByChat, chatId: string): ChatMessage[] => all[chatId] ?? NONE;

export const putMessages = (all: MessagesByChat, chatId: string, update: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])): MessagesByChat => ({
  ...all,
  [chatId]: typeof update === "function" ? update(messagesOf(all, chatId)) : update,
});

/**
 * A chat was opened and the server sent its messages. Only the chats whose answer is still being written keep their list besides it: the
 * server stores a question and its answer when the answer is complete, so until then the list on screen is the only place they exist.
 * Every other chat is shown from the server again the next time it is opened.
 */
export const loadedMessages = (all: MessagesByChat, chatId: string, fromServer: ChatMessage[], answering: StageByChat): MessagesByChat => {
  const kept: MessagesByChat = {};
  for (const id of Object.keys(answering)) if (id in all) kept[id] = all[id];
  return { ...kept, [chatId]: chatId in answering ? messagesOf(all, chatId) : fromServer };
};

/** D7: a page of older messages goes before the ones a chat shows (one already shown is not repeated). Only for a chat whose list is kept. */
export const olderMessages = (all: MessagesByChat, chatId: string, older: ChatMessage[]): MessagesByChat => {
  if (!(chatId in all)) return all;
  const shown = new Set(all[chatId].map((m) => m.message_id));
  return { ...all, [chatId]: [...older.filter((m) => !shown.has(m.message_id)), ...all[chatId]] };
};

/** The message_index to ask for the page before (the oldest message shown); null when the oldest one was never stored with a position. */
export const pageCursor = (messages: Pick<ChatMessage, "message_id" | "message_index">[]): number | null =>
  typeof messages[0]?.message_index === "number" ? messages[0].message_index : null;

/** How many messages a page holds: even, so a page never splits a question from its answer (they are stored together). */
export const MESSAGE_PAGE = 30;

/** A full page whose oldest message is not the chat's first: there may be older ones. */
export const hasOlderPage = (page: Pick<ChatMessage, "message_id" | "message_index">[], size: number): boolean =>
  page.length >= size && (pageCursor(page) ?? 0) > 0;

export const startAnswering = (st: StageByChat, chatId: string): StageByChat => ({ ...st, [chatId]: "understanding" });

/** A stage event of an answer that already finished is ignored: it must not bring the chat back to "answering". */
export const moveStage = (st: StageByChat, chatId: string, stage: ChatStage): StageByChat => (chatId in st ? { ...st, [chatId]: stage } : st);

export const doneAnswering = (st: StageByChat, chatId: string): StageByChat => {
  const { [chatId]: _done, ...rest } = st;
  return rest;
};
