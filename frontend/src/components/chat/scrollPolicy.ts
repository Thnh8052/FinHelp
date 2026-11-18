// When the message list scrolls. Pure functions (no DOM), tested by scripts/test-scroll.mjs.

/** How far from the end of the list still counts as "at the end" (px). */
export const END_GAP_PX = 48;

export interface ScrollSnapshot {
  chatKey: string;
  count: number;
  /** the newest question: a new one means the reader just asked something */
  lastUserId: string;
}

export const snapshotOf = (chatKey: string, messages: { message_id: string; role: string }[]): ScrollSnapshot => ({
  chatKey,
  count: messages.length,
  lastUserId: [...messages].reverse().find((m) => m.role === "user")?.message_id ?? "",
});

export interface ScrollStep {
  to: "top" | "bottom" | "stay";
  /** the list is (or should now count as being) at its end */
  pinned: boolean;
}

/**
 * What to do after the messages changed. Only these move the reader: no messages (the start screen is read from the top), a chat that was
 * just opened or loaded, a question just asked. Any other change (a flag on an old answer, the text of the answer being written, the stored
 * answer replacing it) leaves a reader who scrolled up where they are, and follows the text only for a reader who is at the end.
 */
export function scrollAfterChange(prev: ScrollSnapshot | null, next: ScrollSnapshot, pinned: boolean): ScrollStep {
  if (next.count === 0) return { to: "top", pinned: false };
  if (!prev || prev.chatKey !== next.chatKey || prev.count === 0) return { to: "bottom", pinned: true };
  if (next.lastUserId !== prev.lastUserId) return { to: "bottom", pinned: true };
  return { to: pinned ? "bottom" : "stay", pinned };
}

/**
 * Whether the list is pinned to its end after a scroll event. A smooth scroll that is still on its way down while the content grows leaves a
 * large gap but the position never goes up: that is not the reader leaving the end. Only a move up unpins.
 */
export function pinnedAfterScroll(pinned: boolean, s: { gap: number; top: number; lastTop: number }): boolean {
  if (s.gap < END_GAP_PX) return true;
  return s.top < s.lastTop ? false : pinned;
}
