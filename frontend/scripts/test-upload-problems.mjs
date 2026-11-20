// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of the one message a batch of files left out gets (src/utils/uploadProblems.ts). No browser, no backend.
//
//   node scripts/test-upload-problems.mjs
import assert from "node:assert/strict";
import { mergeProblems } from "../src/utils/uploadProblems.ts";

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

const texts = { several: "{n} files were not uploaded:", more: "and {n} more" };
const warn = (message) => ({ message, level: "warning" });
const err = (message) => ({ message, level: "error" });

check("no problem: nothing to show", () => {
  assert.equal(mergeProblems([], texts), null);
});
check("one problem is shown as it is", () => {
  const p = warn("a.pdf already exists");
  assert.deepEqual(mergeProblems([p], texts), p);
});
check("several problems become one message that lists every file", () => {
  const out = mergeProblems([warn("a.pdf already exists"), warn("b.pdf is too large"), err("c.pdf is not a valid PDF")], texts);
  assert.equal(out.message, "3 files were not uploaded:\n• a.pdf already exists\n• b.pdf is too large\n• c.pdf is not a valid PDF");
});
check("the worst level wins: one error makes the whole message an error", () => {
  assert.equal(mergeProblems([warn("a"), err("b")], texts).level, "error");
  assert.equal(mergeProblems([warn("a"), warn("b")], texts).level, "warning");
});
check("more than three: the first three are listed, the rest are counted", () => {
  const out = mergeProblems(["a", "b", "c", "d", "e"].map(warn), texts);
  assert.equal(out.message, "5 files were not uploaded:\n• a\n• b\n• c\nand 2 more");
});
check("the same message twice is said once", () => {
  const out = mergeProblems([warn("a.pdf already exists"), warn("a.pdf already exists"), warn("b.pdf is too large")], texts);
  assert.equal(out.message, "2 files were not uploaded:\n• a.pdf already exists\n• b.pdf is too large");
});
check("a problem that names its file (a server error) shows the name in the list, so each line says which file; alone it stays as it is", () => {
  const bad = (file, message) => ({ message, level: "warning", file });
  const out = mergeProblems([bad("notes.txt", "Only PDF files are supported."), bad("fake.pdf", "This file is not a valid PDF."), bad("second.pdf", "This file is not a valid PDF.")], texts);
  assert.equal(out.message, ["3 files were not uploaded:", "• notes.txt: Only PDF files are supported.", "• fake.pdf: This file is not a valid PDF.", "• second.pdf: This file is not a valid PDF."].join("\n"));
  const alone = bad("fake.pdf", "This file is not a valid PDF.");
  assert.equal(mergeProblems([alone], texts).message, "This file is not a valid PDF.");
});
check("a sign-in action is kept, so the button still shows", () => {
  const onAction = () => {};
  const out = mergeProblems([warn("a"), { message: "guest limit", level: "warning", actionLabel: "Sign in", onAction }], texts);
  assert.equal(out.actionLabel, "Sign in");
  assert.equal(out.onAction, onAction);
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
