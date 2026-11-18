// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of when the message list scrolls (src/components/chat/scrollPolicy.ts). No browser, no backend, no model call.
//
//   node scripts/test-scroll.mjs
import assert from "node:assert/strict";
import { pinnedAfterScroll, scrollAfterChange, snapshotOf } from "../src/components/chat/scrollPolicy.ts";

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

const user = (id) => ({ message_id: id, role: "user", content: "q" });
const answer = (id) => ({ message_id: id, role: "assistant", content: "a" });
const snap = (chatKey, messages) => snapshotOf(chatKey, messages);

// ---------------------------------------------------------------- what the list does after its messages changed
check("no messages: the start screen is read from the top, not pinned", () => {
  const r = scrollAfterChange(snap("a", [user("u1")]), snap("a", []), true);
  assert.deepEqual(r, { to: "top", pinned: false });
});
check("a chat's messages arrive after the list was empty: jump to the end and pin", () => {
  const r = scrollAfterChange(snap("a", []), snap("a", [user("u1"), answer("a1")]), false);
  assert.deepEqual(r, { to: "bottom", pinned: true });
});
check("another chat opened: jump to the end and pin, even if the reader had scrolled up", () => {
  const r = scrollAfterChange(snap("a", [user("u1"), answer("a1")]), snap("b", [user("u2"), answer("a2")]), false);
  assert.deepEqual(r, { to: "bottom", pinned: true });
});
check("the reader asks a question while scrolled up: jump to the end and pin", () => {
  const before = [user("u1"), answer("a1")];
  const r = scrollAfterChange(snap("a", before), snap("a", [...before, user("u2")]), false);
  assert.deepEqual(r, { to: "bottom", pinned: true });
});
check("a button asks a question again (a new question is added): jump to the end", () => {
  const before = [user("u1"), answer("a1")];
  const r = scrollAfterChange(snap("a", before), snap("a", [...before, user("u2"), answer("a2")]), false);
  assert.equal(r.to, "bottom");
});
check("F1: 'Report wrong figures' changes an old answer while the reader is scrolled up: stay", () => {
  const before = [user("u1"), answer("a1"), user("u2"), answer("a2")];
  const flagged = before.map((m) => (m.message_id === "a1" ? { ...m, user_rating: -1 } : m));
  const r = scrollAfterChange(snap("a", before), snap("a", flagged), false);
  assert.deepEqual(r, { to: "stay", pinned: false });
});
check("F2: the answer being written grows while the reader is scrolled up: stay, stay unpinned", () => {
  const before = [user("u1"), { ...answer("s1"), content: "Hel" }];
  const after = [user("u1"), { ...answer("s1"), content: "Hello wor" }];
  const r = scrollAfterChange(snap("a", before), snap("a", after), false);
  assert.deepEqual(r, { to: "stay", pinned: false });
});
check("the answer being written grows while the reader is at the end: keep following", () => {
  const before = [user("u1"), { ...answer("s1"), content: "Hel" }];
  const after = [user("u1"), { ...answer("s1"), content: "Hello wor" }];
  const r = scrollAfterChange(snap("a", before), snap("a", after), true);
  assert.deepEqual(r, { to: "bottom", pinned: true });
});
check("the stored answer replaces the streamed one (new id, same count): the pin decides", () => {
  const before = [user("u1"), answer("s1")];
  const after = [user("u1"), answer("m1")];
  assert.equal(scrollAfterChange(snap("a", before), snap("a", after), false).to, "stay");
  assert.equal(scrollAfterChange(snap("a", before), snap("a", after), true).to, "bottom");
});
check("the very first snapshot (nothing before it): jump to the end", () => {
  assert.equal(scrollAfterChange(null, snap("a", [user("u1")]), false).to, "bottom");
});

// ---------------------------------------------------------------- when the reader counts as being at the end
check("at the end: pinned", () => {
  assert.equal(pinnedAfterScroll(false, { gap: 0, top: 500, lastTop: 400 }), true);
  assert.equal(pinnedAfterScroll(false, { gap: 47, top: 500, lastTop: 400 }), true);
});
check("the reader scrolls up: unpinned", () => {
  assert.equal(pinnedAfterScroll(true, { gap: 300, top: 200, lastTop: 500 }), false);
});
check("the content grows under a smooth scroll that is still moving down: stays pinned (the gap is large, the position did not go up)", () => {
  assert.equal(pinnedAfterScroll(true, { gap: 900, top: 520, lastTop: 500 }), true);
});
check("the reader scrolls down but not to the end: an unpinned list stays unpinned", () => {
  assert.equal(pinnedAfterScroll(false, { gap: 600, top: 300, lastTop: 200 }), false);
});

console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
