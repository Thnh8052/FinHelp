// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of the per-chat message lists and "answering" marks (src/hooks/chatStore.ts). No browser, no backend, no model call.
//
//   node scripts/test-chat-store.mjs
import assert from "node:assert/strict";
import { doneAnswering, loadedMessages, messagesOf, moveStage, putMessages, startAnswering } from "../src/hooks/chatStore.ts";

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
