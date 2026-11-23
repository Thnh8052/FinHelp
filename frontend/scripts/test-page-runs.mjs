// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of how the document card lists the pages to check (src/components/notebook/pageRuns.ts): consecutive pages become one range, the list is cut
// after `max` ranges. No browser, no backend.
//
//   node scripts/test-page-runs.mjs
import assert from "node:assert/strict";
import { pageRuns } from "../src/components/notebook/pageRuns.ts";

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

check("consecutive pages become one range, the rest stay single", () => {
  assert.deepEqual(pageRuns([6, 7, 8, 9, 34, 137]), { runs: [{ first: 6, last: 9 }, { first: 34, last: 34 }, { first: 137, last: 137 }], more: 0 });
});
check("pages arrive in any order and twice", () => {
  assert.deepEqual(pageRuns([12, 3, 4, 12]), { runs: [{ first: 3, last: 4 }, { first: 12, last: 12 }], more: 0 });
});
check("after max ranges the others are counted, not listed", () => {
  assert.deepEqual(pageRuns([1, 3, 5, 7, 9], 3), { runs: [{ first: 1, last: 1 }, { first: 3, last: 3 }, { first: 5, last: 5 }], more: 2 });
});
check("no pages, no runs", () => {
  assert.deepEqual(pageRuns([]), { runs: [], more: 0 });
  assert.deepEqual(pageRuns(undefined), { runs: [], more: 0 });
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
