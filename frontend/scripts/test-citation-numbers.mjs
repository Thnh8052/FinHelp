// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of the numbers shown for an answer's citations (src/utils/citationNumbers.ts): 1, 2, 3 in the order the text meets them, the excerpt behind each
// number unchanged. No browser, no backend.
//
//   node scripts/test-citation-numbers.mjs
import assert from "node:assert/strict";
import { displayNumbers, renumber } from "../src/utils/citationNumbers.ts";

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
const shown = (content, cited) => Object.fromEntries(displayNumbers(content, cited));

check("production check 20/11: [1] and [5] are shown as 1 and 2", () => {
  assert.deepEqual(shown("Intel [1] and Salesforce [5].", [1, 5]), { 1: 1, 5: 2 });
});
check("numbers follow the order the text meets them, not the order of the excerpts", () => {
  assert.deepEqual(shown("First [5], then [1].", [1, 5]), { 5: 1, 1: 2 });
});
check("a number said again keeps its place", () => {
  assert.deepEqual(shown("A [5][5] B [1] C [5]", [1, 5]), { 5: 1, 1: 2 });
});
check("citations in a table header ([2][5]) are numbered like the text", () => {
  assert.deepEqual(shown("| Year [2][5] |\n| 10 [2] |", [2, 5]), { 2: 1, 5: 2 });
});
check("a cited excerpt the text never names comes last, so every card still has a number", () => {
  assert.deepEqual(shown("Only [4] here.", [4, 7, 9]), { 4: 1, 7: 2, 9: 3 });
});
check("a number in the text with no excerpt keeps a place too, so no two excerpts share a number", () => {
  assert.deepEqual(shown("See [9] and [3].", [3]), { 9: 1, 3: 2 });
});
check("no citation at all: nothing to number", () => {
  assert.deepEqual(shown("No sources here.", []), {});
});
check("renumber rewrites every [n] once (no chain: 1 -> 2 does not become 3)", () => {
  const map = displayNumbers("A [2] B [1] C [3]", [1, 2, 3]);
  assert.equal(renumber("A [2] B [1] C [3]", map), "A [1] B [2] C [3]");
  assert.equal(renumber("A [5] B [1] C [5]", displayNumbers("A [5] B [1] C [5]", [1, 5])), "A [1] B [2] C [1]");
});
check("renumber leaves text without brackets and other brackets alone", () => {
  const text = "Revenue (USD) [5] grew [see note]";
  assert.equal(renumber(text, displayNumbers(text, [5])), "Revenue (USD) [1] grew [see note]");
});

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log("\nall passed");
