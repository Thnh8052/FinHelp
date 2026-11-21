// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// The steps of one answer on the admin page (src/features/admin/stepsView.ts): the request path, the words for a decision code and for the short facts of a step.
// No browser, no backend.
//
//   node scripts/test-admin-steps.mjs
import assert from "node:assert/strict";
import { codeText, describeFacts, outcomeTone, rate, stepsPath, summaryPath, summaryRows } from "../src/features/admin/stepsView.ts";

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
check("a code, alone or in a list, is said in words when there are words for it (a third argument), else it shows as it is", () => {
  const words = { short: "the answer fell short", plan_deadline: "the planner was too slow", not_waited: "not waited for" };
  assert.deepEqual(describeFacts({ why: ["short", "chose_for_user"], degraded: ["plan_deadline"], result: "not_waited", routing: "targets_planner" },
    { why: "Why", degraded: "Dropped", result: "Result", routing: "Chosen by" }, words),
    [["Why", "the answer fell short, chose_for_user"], ["Dropped", "the planner was too slow"], ["Result", "not waited for"], ["Chosen by", "targets_planner"]]);
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

// ---- the steps of many answers added up (GET /auth/admin/steps-summary)
check("the summary request carries the window and the user filter", () => {
  assert.equal(summaryPath(14, ""), "/auth/admin/steps-summary?days=14");
  assert.equal(summaryPath(7, "usr_1"), "/auth/admin/steps-summary?days=7&user=usr_1");
  assert.equal(summaryPath(7, "a&b"), "/auth/admin/steps-summary?days=7&user=a%26b");
});
const summary = {
  questions: 10, answered: 7, stopped: { guard: 2, input: 1 },
  seconds: { guard: { n: 9, p50: 1.1, p90: 1.8 }, plan: { n: 7, p50: 3.5, p90: 7 } },
  guard: { labels: { ok: 7, personal_advice: 2 }, outcomes: { passed: 7, kept: 2, not_waited: 1 }, waited: { answers: 7, over_half_second: 1 } },
  degraded: {}, search_deeper: { offered: 7, prominent: 1, clicks: 2 },
};
check("one row per step in order, with zeros and blanks where a step has no data", () => {
  const rows = summaryRows(summary, ["gate", "input", "guard", "plan"]);
  assert.deepEqual(rows.map((r) => r.step), ["gate", "input", "guard", "plan"]);
  assert.deepEqual(rows[2], { step: "guard", stopped: 2, n: 9, p50: 1.1, p90: 1.8 });
  assert.deepEqual(rows[0], { step: "gate", stopped: 0, n: null, p50: null, p90: null });
  assert.equal(rows[1].stopped, 1);
});
check("a share is a whole percent, or a dash when there is nothing to divide", () => {
  assert.equal(rate(1, 7), "14 %");
  assert.equal(rate(2, 7), "29 %");
  assert.equal(rate(0, 0), "–");
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
