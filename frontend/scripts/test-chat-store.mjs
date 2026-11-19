// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of the per-chat message lists and "answering" marks (src/hooks/chatStore.ts). No browser, no backend, no model call.
//
//   node scripts/test-chat-store.mjs
import assert from "node:assert/strict";
import { doneAnswering, hasOlderPage, loadedMessages, MESSAGE_PAGE, messagesOf, moveStage, olderMessages, pageCursor, putMessages, startAnswering } from "../src/hooks/chatStore.ts";

let failed = 0;
const check = (name, fn) => {
  try {
    fn();
    console.log("PASS ", name);
  } catch (e) {
    failed++;
    console.log("FAIL ", name, "\n      ", e.message.split("\n")[0]);
  }
};

const msg = (id, nb, role = "user", content = "x") => ({ message_id: id, notebook_id: nb, role, content });

// ---------------------------------------------------------------- the lists
check("a chat nobody wrote to has no messages (and always the same empty list)", () => {
  assert.deepEqual(messagesOf({}, "a"), []);
  assert.equal(messagesOf({}, "a"), messagesOf({}, "b"));
});
check("writing to chat A leaves chat B's list as it was", () => {
  const b = [msg("b1", "b")];
  const all = putMessages({ b }, "a", [msg("a1", "a")]);
  assert.equal(all.b, b);
  assert.deepEqual(messagesOf(all, "a").map((m) => m.message_id), ["a1"]);
});
check("an update function gets the messages of that chat only", () => {
  const seen = [];
  const start = { a: [msg("a1", "a")], b: [msg("b1", "b")] };
  const all = putMessages(start, "a", (prev) => {
    seen.push(prev.map((m) => m.message_id));
    return [...prev, msg("a2", "a", "assistant")];
  });
  assert.deepEqual(seen, [["a1"]]);
  assert.deepEqual(messagesOf(all, "a").map((m) => m.message_id), ["a1", "a2"]);
  assert.equal(all.b, start.b);
});
check("F3: the answer of chat A arrives while chat B is open: it lands in A, B has none of it", () => {
  let all = putMessages({}, "b", [msg("b1", "b")]);
  all = putMessages(all, "a", (p) => [...p, msg("q", "a"), msg("streaming", "a", "assistant", "partial")]);   // the reader asked in A, then opened B
  all = putMessages(all, "a", (p) => p.map((m) => (m.message_id === "streaming" ? { ...m, content: "full answer" } : m)));  // the answer keeps coming
  assert.deepEqual(messagesOf(all, "b").map((m) => m.message_id), ["b1"]);
  assert.equal(messagesOf(all, "a").find((m) => m.message_id === "streaming").content, "full answer");
});
check("the input is not mutated", () => {
  const a = [msg("a1", "a")];
  const start = { a };
  putMessages(start, "a", (p) => [...p, msg("a2", "a")]);
  assert.equal(start.a, a);
  assert.equal(a.length, 1);
});

// ---------------------------------------------------------------- opening a chat (its messages come from the server)
check("opening a chat shows the server's messages and drops the lists of chats left behind", () => {
  const all = { a: [msg("a1", "a")], b: [] };
  const after = loadedMessages(all, "b", [msg("b1", "b")], {});
  assert.deepEqual(Object.keys(after), ["b"]);
  assert.deepEqual(messagesOf(after, "b").map((m) => m.message_id), ["b1"]);
});
check("a chat whose answer is still being written keeps its list when another chat is opened", () => {
  const live = [msg("a1", "a"), msg("q", "a"), msg("streaming", "a", "assistant", "partial")];
  const after = loadedMessages({ a: live }, "b", [msg("b1", "b")], { a: "writing" });
  assert.equal(after.a, live);
  assert.deepEqual(messagesOf(after, "b").map((m) => m.message_id), ["b1"]);
});
check("F3: coming back to A while it still answers keeps what A shows (the server has not stored the question yet)", () => {
  const live = [msg("a1", "a"), msg("q", "a"), msg("streaming", "a", "assistant", "partial")];
  const serverNow = [msg("a1", "a")];   // the server stores the question and the answer only when the answer is complete
  const after = loadedMessages({ a: live }, "a", serverNow, { a: "writing" });
  assert.equal(after.a, live);
});
check("coming back to A after it finished shows the server's list, which has the answer", () => {
  const live = [msg("a1", "a"), msg("q", "a"), msg("final", "a", "assistant", "full")];
  const serverNow = [msg("a1", "a"), msg("q2", "a"), msg("final", "a", "assistant", "full")];
  const after = loadedMessages({ a: live }, "a", serverNow, {});
  assert.equal(after.a, serverNow);
});

// ---------------------------------------------------------------- D7: a long chat is read a page at a time
check("older messages go before the ones shown, without repeating one", () => {
  const all = { a: [msg("m3", "a"), msg("m4", "a", "assistant")] };
  const after = olderMessages(all, "a", [msg("m1", "a"), msg("m2", "a", "assistant"), msg("m3", "a")]);
  assert.deepEqual(messagesOf(after, "a").map((m) => m.message_id), ["m1", "m2", "m3", "m4"]);
});
check("older messages of a chat left behind are dropped (it is read again when opened)", () => {
  const after = olderMessages({ b: [msg("b1", "b")] }, "a", [msg("m1", "a")]);
  assert.deepEqual(Object.keys(after), ["b"]);
});
check("the page before the oldest message starts below its message_index; none without one", () => {
  assert.equal(pageCursor([{ message_id: "x", message_index: 30 }, { message_id: "y", message_index: 31 }]), 30);
  assert.equal(pageCursor([{ message_id: "msg_user_1" }]), null);  // a question asked in this visit: nothing older is known to be stored
  assert.equal(pageCursor([]), null);
});

check("a full page that does not start at the chat's first message may have older ones; a short page or one from 0 has none", () => {
  const page = (from, n) => Array.from({ length: n }, (_, i) => ({ message_id: `m${from + i}`, message_index: from + i }));
  assert.equal(hasOlderPage(page(30, 30), 30), true);
  assert.equal(hasOlderPage(page(0, 30), 30), false);  // exactly one page: the button would load nothing
  assert.equal(hasOlderPage(page(10, 12), 30), false);
  assert.equal(MESSAGE_PAGE % 2, 0);  // a question and its answer are stored together: an even page never splits them
});

// ---------------------------------------------------------------- which chats are being answered, and at which stage
check("F3: an answer running in A does not lock chat B", () => {
  const st = startAnswering({}, "a");
  assert.equal("a" in st, true);
  assert.equal("b" in st, false);
});
check("a stage event moves only the chat it belongs to", () => {
  let st = startAnswering(startAnswering({}, "a"), "b");
  st = moveStage(st, "a", "writing");
  assert.equal(st.a, "writing");
  assert.equal(st.b, "understanding");
});
check("a stage event that arrives after the answer finished does not bring the chat back to 'answering'", () => {
  const st = doneAnswering(startAnswering({}, "a"), "a");
  assert.deepEqual(moveStage(st, "a", "checking"), {});
});
check("finishing A leaves B answering", () => {
  const st = doneAnswering(startAnswering(startAnswering({}, "a"), "b"), "a");
  assert.deepEqual(Object.keys(st), ["b"]);
});
check("asking again in A while A is answering (not possible from the box, but safe): back to the first stage", () => {
  const st = startAnswering(moveStage(startAnswering({}, "a"), "a", "writing"), "a");
  assert.equal(st.a, "understanding");
});

console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
