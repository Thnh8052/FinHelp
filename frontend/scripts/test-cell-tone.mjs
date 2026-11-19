// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of how a table cell of an answer is coloured (src/components/chat/cellTone.ts). No browser, no backend, no model call.
//
//   node scripts/test-cell-tone.mjs
import assert from "node:assert/strict";
import { cellTone, isLongHeader, isNumericCell } from "../src/components/chat/cellTone.ts";

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

// ---------------------------------------------------------------- only a signed figure is coloured
check("F9: a margin or share (a plain percentage) is not coloured", () => {
  for (const cell of ["2.1%", "5.3%", "12.9%", "100%", "61.3% [2]"]) assert.equal(cellTone(cell), "", cell);
});
check("F9: a label that mentions % or a word is not coloured", () => {
  for (const cell of ["Operating margin (%)", "Biên lợi nhuận hoạt động (%)", "Decrease in net sales", "giảm 5%", "Margin of 12% was cited"]) assert.equal(cellTone(cell), "", cell);
});
check("a plain figure is not coloured", () => {
  for (const cell of ["177,866 [5]", "$ 4,051,189", "2,233", "1.5x"]) assert.equal(cellTone(cell), "", cell);
});
check("a figure with a plus sign is a rise", () => {
  for (const cell of ["+12.4%", "+30.9% [5]", "+$1,200", "+ 3.5%"]) assert.equal(cellTone(cell), "positive", cell);
});
check("a figure with a minus sign (hyphen, minus, en dash) is a fall", () => {
  for (const cell of ["-3.2%", "−3.2%", "–3.2% [2]", "-$5", "−1,234"]) assert.equal(cellTone(cell), "negative", cell);
});
check("a figure in brackets is a fall, as in accounts: (1.1%), (1,204) [2][3], $ (5)", () => {
  for (const cell of ["(1.1%)", "(1,204) [2][3]", "$ (5)", "(5)"]) assert.equal(cellTone(cell), "negative", cell);
});
check("an empty cell (a dash, N/A) is marked empty, not as a fall", () => {
  for (const cell of ["—", "-", "–", "−", "N/A", "n/a"]) assert.equal(cellTone(cell), "empty", cell);
});
check("text that starts with a sign but is not a figure is not coloured", () => {
  for (const cell of ["-ish", "+ see note", "(USD million)", "(a) restated"]) assert.equal(cellTone(cell), "", cell);
});
check("surrounding spaces do not matter", () => {
  assert.equal(cellTone("  +12.4%  "), "positive");
  assert.equal(cellTone("  12.4%  "), "");
});

// ---------------------------------------------------------------- which cells stay on one line (figures with their citations)
check("a figure with its citations is numeric; a name or a sentence is not", () => {
  assert.equal(isNumericCell("177,866 [5]"), true);
  assert.equal(isNumericCell("+30.9%"), true);
  assert.equal(isNumericCell("(1,204) [2][3]"), true);
  assert.equal(isNumericCell("Costco Wholesale Corporation"), false);
  assert.equal(isNumericCell("FY2018"), false);
});

// ---------------------------------------------------------------- headers that need a wider column
check("C8: a long header title gets a wide column, a short one keeps the narrow one", () => {
  assert.equal(isLongHeader("Thay đổi biên lợi nhuận hoạt động 2015–2020"), true);
  assert.equal(isLongHeader("Change in operating margin 2015–2020"), true);
  for (const title of ["FY2018", "Công ty", "Chỉ tiêu", "Net sales", "Costco Wholesale"]) assert.equal(isLongHeader(title), false, title);
});
check("the length of a header is counted without the spaces around it", () => {
  assert.equal(isLongHeader("   FY2018   "), false);
});

console.log(failed ? `\n${failed} FAILED` : "\nall passed");
process.exit(failed ? 1 : 0);
