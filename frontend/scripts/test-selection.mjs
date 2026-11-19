// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of which reports are ticked when a chat is opened (src/types/notebook.ts, defaultSelection). No browser, no backend, no model call.
//
//   node scripts/test-selection.mjs
import assert from "node:assert/strict";
import { defaultSelection } from "../src/types/notebook.ts";

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

const doc = (id, status = "ready") => ({ document_id: id, status });

check("F4: a chat with 5 ready reports opens with all 5 ticked, not only the first", () => {
  const docs = ["a", "b", "c", "d", "e"].map((id) => doc(id));
  assert.deepEqual(defaultSelection(docs, 5), ["a", "b", "c", "d", "e"]);
});
check("only ready reports are ticked (processing and failed ones are left out)", () => {
  const docs = [doc("a", "processing"), doc("b"), doc("c", "failed"), doc("d", "pending"), doc("e")];
  assert.deepEqual(defaultSelection(docs, 5), ["b", "e"]);
});
check("never more than the account allows: the last ones are kept, like 'select all'", () => {
  const docs = ["a", "b", "c", "d", "e"].map((id) => doc(id));
  assert.deepEqual(defaultSelection(docs, 3), ["c", "d", "e"]);
});
check("a guest (1 report) gets one ready report", () => {
  assert.deepEqual(defaultSelection([doc("a"), doc("b")], 1), ["b"]);
});
check("nothing ready: nothing ticked", () => {
  assert.deepEqual(defaultSelection([doc("a", "processing")], 5), []);
  assert.deepEqual(defaultSelection([], 5), []);
});

console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
