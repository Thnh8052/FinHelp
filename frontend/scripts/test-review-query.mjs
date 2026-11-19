// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// The admin review page: the request it sends for its filters, and the tone of each problem label (src/features/admin/reviewQuery.ts).
//
//   node scripts/test-review-query.mjs
import assert from "node:assert/strict";
import { labelTone, reviewPath } from "../src/features/admin/reviewQuery.ts";

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

check("everyone, every problem, open: only the window", () => assert.equal(reviewPath({ days: 14, user: "", label: "", status: "open" }), "/auth/admin/review?days=14&status=open"));
check("one user, one problem, reviewed", () =>
  assert.equal(reviewPath({ days: 30, user: "usr_1", label: "not_found", status: "reviewed" }), "/auth/admin/review?days=30&status=reviewed&label=not_found&user=usr_1"));
check("the guests filter is sent as it is", () => assert.equal(reviewPath({ days: 7, user: "guests", label: "", status: "all" }), "/auth/admin/review?days=7&status=all&user=guests"));
check("a user id is escaped", () => assert.match(reviewPath({ days: 7, user: "a&b", label: "", status: "open" }), /user=a%26b$/));
check("what the user reported or what was blocked is red; a warning or a partial answer amber; the rest neutral", () => {
  assert.deepEqual(["user_report", "blocked"].map(labelTone), ["negative", "negative"]);
  assert.deepEqual(["warning", "partial", "not_found", "refused", "degraded", "slow"].map(labelTone), ["warn", "warn", "warn", "warn", "neutral", "neutral"]);
  assert.equal(labelTone("not_traced"), "warn"); // figures or citations the checks could not trace: hidden from the user since 19/11, so the admin looks
  assert.equal(labelTone("safety"), "neutral");
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
