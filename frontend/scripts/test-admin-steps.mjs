// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// The steps of one answer on the admin page (src/features/admin/stepsView.ts): the request path, the words for a decision code and for the short facts of a step.
// No browser, no backend.
//
//   node scripts/test-admin-steps.mjs
import assert from "node:assert/strict";
import { codeText, describeFacts, outcomeTone, stepsPath } from "../src/features/admin/stepsView.ts";

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

check("the request path escapes the message id", () => {
  assert.equal(stepsPath("msg_1"), "/auth/admin/steps/msg_1");
  assert.equal(stepsPath("a/b c"), "/auth/admin/steps/a%2Fb%20c");
});

const names = { documents: "Documents", routing: "Chosen by", rerank_seconds: "Rerank", degraded: "Dropped steps", edit_question: "Edit the question" };

check("facts become label and value pairs in the order they came", () => {
  const out = describeFacts({ documents: 2, routing: "targets_planner", rerank_seconds: 0.6 }, names);
  assert.deepEqual(out, [["Documents", "2"], ["Chosen by", "targets_planner"], ["Rerank", "0.6 s"]]);
});
check("a list is joined, a true flag is a tick, a key with no label shows its own name", () => {
  const out = describeFacts({ degraded: ["plan_deadline", "rerank_skipped"], edit_question: true, mystery: "x" }, names);
  assert.deepEqual(out, [["Dropped steps", "plan_deadline, rerank_skipped"], ["Edit the question", "✓"], ["mystery", "x"]]);
});
check("no facts, no pairs", () => assert.deepEqual(describeFacts({}, names), []));

const codes = { guard: { personal_advice: "Personal advice", ok: "Question about the reports" }, input: { period_unavailable: "Year not in the reports" } };

check("a decision code is said in words, per step; an unknown code shows as it is; no code shows nothing", () => {
  assert.equal(codeText(codes, "guard", "personal_advice"), "Personal advice");
  assert.equal(codeText(codes, "input", "period_unavailable"), "Year not in the reports");
  assert.equal(codeText(codes, "guard", "new_label"), "new_label");
  assert.equal(codeText(codes, "plan", "planned"), "planned");
  assert.equal(codeText(codes, "guard", null), "");
});
check("a stopped step is red, a warning amber, the rest quiet", () => {
  assert.deepEqual(["ok", "warn", "stopped", "skipped"].map(outcomeTone), ["neutral", "warn", "negative", "neutral"]);
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
