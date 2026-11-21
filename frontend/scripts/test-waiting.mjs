// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// What the wait before an answer says (src/components/chat/waiting.ts): the stage line, the stage bar, and for the "analyzing" stage (the model's first reasoning piece, T6a)
// the seconds counted from there. No browser, no backend.
//
//   node scripts/test-waiting.mjs
import assert from "node:assert/strict";
import { barIndex, STAGES, waitingText } from "../src/components/chat/waiting.ts";

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

const texts = {
  stages: { understanding: "Reading your question...", searching: "Searching the documents...", writing: "Writing...", analyzing: "Analyzing the figures · {s} s", checking: "Checking the answer..." },
  slow: "This question needs a little more time...",
  click: { deeper: "Searching deeper..." },
};
const say = (o) => waitingText({ stage: "searching", slow: false, click: "", seconds: 0, texts, ...o });

check("each stage says its own line", () => {
  assert.equal(say({ stage: "understanding" }), "Reading your question...");
  assert.equal(say({ stage: "writing" }), "Writing...");
  assert.equal(say({ stage: "checking" }), "Checking the answer...");
});
check("the analyzing stage counts the seconds from the model's first reasoning piece", () => {
  assert.equal(say({ stage: "analyzing", seconds: 0 }), "Analyzing the figures · 0 s");
  assert.equal(say({ stage: "analyzing", seconds: 27 }), "Analyzing the figures · 27 s");
});
check("a stage that lasts long says so, but not analyzing: its clock already shows that nothing hung", () => {
  assert.equal(say({ stage: "searching", slow: true }), "This question needs a little more time...");
  assert.equal(say({ stage: "analyzing", slow: true, seconds: 31 }), "Analyzing the figures · 31 s");
});
check("after a click the search stages say what the click does; the later stages do not", () => {
  assert.equal(say({ stage: "searching", click: "deeper" }), "Searching deeper...");
  assert.equal(say({ stage: "understanding", click: "deeper" }), "Searching deeper...");
  assert.equal(say({ stage: "writing", click: "deeper" }), "Writing...");
  assert.equal(say({ stage: "analyzing", click: "deeper", seconds: 4 }), "Analyzing the figures · 4 s");
});
check("the stage bar has four steps and analyzing is part of the writing step", () => {
  assert.deepEqual(STAGES, ["understanding", "searching", "writing", "checking"]);
  assert.deepEqual(["understanding", "searching", "writing", "analyzing", "checking"].map(barIndex), [0, 1, 2, 2, 3]);
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
