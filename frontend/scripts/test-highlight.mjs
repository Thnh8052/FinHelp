// Needs Node 22.18 or newer: it imports the TypeScript module as it is (type stripping), no build step.
// Tests of the citation highlight (src/components/notebook/locateExcerpt.ts). No browser, no backend, no model call.
//
//   node scripts/test-highlight.mjs                 # fixed cases, then the real-page check when the experiment data is on this machine
//   node scripts/test-highlight.mjs --pages 40      # how many table pages the real-page check samples (default 30)
//
// Real-page check: for pages of the experiment PDFs (experiments/data/pdfs), the parser's own Markdown of the page is cut like the backend cuts a citation
// snippet (clip_snippet: 1,200 characters ending at a line break) and located on the text pdf.js reads from the same page. The same snippet looked up on
// a DIFFERENT page of the same report is the control: it must find (almost) nothing.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bandsFor, citedFigures, excerptUnits, figureLines, locateExcerpt, tokenize } from "../src/components/notebook/locateExcerpt.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
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

// ---------------------------------------------------------------- fixed cases
const item = (str, x, y, width = 40) => ({ str, transform: [10, 0, 0, 10, x, y], width });

check("tokens: numbers lose their separators and signs, words are lower case", () => {
  assert.deepEqual(tokenize("| Total revenue ..... | $ 4,051,189 | (1,111) | 3.5% |"), ["total", "revenue", "4051189", "1111", "3.5"]);
});
check("excerpt lines: table separators and short lines are dropped, long lines are cut", () => {
  const units = excerptUnits("# Title\n|---|---|\n| Net sales | 5,555 |\nx\n" + "word ".repeat(25));
  assert.equal(units.length, 3); // the row, and the long line as pieces of 12 and 12 (the last single word is dropped)
  assert.ok(units.some((u) => u.join(" ") === "net sales 5555"));
  assert.ok(units.every((u) => u.length <= 12));
});
check("a table row is found among rows with the same label, by its numbers", () => {
  const items = [item("Total revenue", 10, 700), item("1,000", 200, 700), item("Total revenue", 10, 600), item("5,555", 200, 600), item("4,444", 260, 600)];
  const r = locateExcerpt("| Total revenue ...... | $ 5,555 | 4,444 |", items);
  assert.deepEqual(r.items, [2, 3, 4]);
  assert.equal(r.found, 1);
});
check("a row whose cells come in another order, with a footnote mark between, is still found", () => {
  const items = [item("4,444", 260, 600), item("(1)", 280, 600), item("Net sales", 10, 600), item("5,555", 200, 600)];
  assert.deepEqual(locateExcerpt("| Net sales | 5,555 | 4,444 |", items).items, [0, 2, 3]);
});
check("text that is not on the page finds nothing", () => {
  const r = locateExcerpt("| Net sales | 5,555 | 4,444 |", [item("Cash and equivalents", 10, 500), item("1,078", 200, 500)]);
  assert.equal(r.found, 0);
  assert.deepEqual(r.items, []);
});
check("one band per row, from the label to the last figure; two rows are two bands; scaled by the viewport", () => {
  const items = [item("Net sales", 10, 700, 50), item("5,555", 300, 700, 30), item("Cost", 10, 680, 20), item("4,444", 300, 680, 30)];
  const bands = bandsFor(items, [0, 1, 2, 3], [2, 0, 0, -2, 0, 1000], 1200); // scale 2 (the page is 600 units, 1200 pixels), flipped: y grows downwards
  assert.equal(bands.length, 2);
  assert.equal(bands[0].left, 20);
  assert.equal(bands[0].width, 2 * 300 + 2 * 30 - 20);
});
check("two columns of text on the same line are not joined into one band", () => {
  const items = [item("left column", 10, 700, 50), item("right column", 560, 700, 50)];
  assert.equal(bandsFor(items, [0, 1], [1, 0, 0, -1, 0, 800], 600).length, 2); // 500 units apart on a 600-unit page
});

check("figures: the numbers of the sentences that cite [n], without years, small counts or other citations", () => {
  const answer = "In the fourth quarter (the 13 weeks ended January 28, 2023), net income was **$340.8 million** ($340,751 thousand), 10.6% of net sales [1][2]. Sales rose 18.2% [3].";
  assert.deepEqual(citedFigures(answer, 1), ["340.8", "340751", "10.6"]);
  assert.deepEqual(citedFigures(answer, 3), ["18.2"]);
  assert.deepEqual(citedFigures(answer, 4), []);
  assert.deepEqual(citedFigures("| Revenue | 5,555 [1] | 4,444 [2] |\nCash was 12 [1].", 2), ["4444"]); // a table row is its own line; 12 alone is a count
});
check("figure lines: the whole row of the figure, in every place it is printed (up to 3), and nothing else", () => {
  const items = [item("Net income", 10, 500), item("$ 340,751", 200, 500), item("10.6%", 260, 500), item("Net sales", 10, 480), item("3,226,773", 200, 480), item("Net income", 10, 300), item("340,751", 200, 300)];
  assert.deepEqual(figureLines(items, ["340751"]), [0, 1, 2, 5, 6]);
  assert.deepEqual(figureLines(items, ["99999"]), []);
  assert.deepEqual(figureLines(items, ["340751"], 1), [0, 1, 2]);
});

// ---------------------------------------------------------------- real pages
const args = process.argv.slice(2);
const sample = Number(args[args.indexOf("--pages") + 1]) || 30;
const pdfDir = path.join(ROOT, "experiments", "data", "pdfs", "eval_84");
const mdDir = path.join(ROOT, "experiments", "outputs", "parsing", "4_postprocessed", "eval_84");

const isFigure = (t) => (/^\d{4,}$/.test(t) && !(Number(t) >= 1990 && Number(t) <= 2035)) || /^\d+\.\d+$/.test(t);

function clip(content, limit = 1200) {
  if (content.length <= limit) return content;
  let cut = content.lastIndexOf("\n", limit);
  if (cut <= 0) cut = content.lastIndexOf(" ", limit);
  return content.slice(0, cut > 0 ? cut : limit).trimEnd();
}

async function realPages() {
  if (!fs.existsSync(pdfDir) || !fs.existsSync(mdDir)) return console.log("SKIP  real-page check: experiment data is not on this machine");
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  const docs = fs.readdirSync(pdfDir).filter((f) => f.endsWith(".pdf")).map((f) => f.slice(0, -4)).filter((d) => fs.existsSync(path.join(mdDir, d, "pages")));
  const perDoc = Math.max(1, Math.ceil(sample / 10));
  const rows = [];
  for (const name of docs.filter((_, i) => i % Math.max(1, Math.floor(docs.length / 10)) === 0).slice(0, 10)) {
    const pdf = await pdfjs.getDocument({ data: new Uint8Array(fs.readFileSync(path.join(pdfDir, name + ".pdf"))), useSystemFonts: true, verbosity: 0 }).promise;
    const pages = fs.readdirSync(path.join(mdDir, name, "pages")).filter((f) => f.endsWith(".md")).sort();
    const tables = pages.filter((f) => fs.readFileSync(path.join(mdDir, name, "pages", f), "utf8").includes("|---")).filter((_, i) => i % 7 === 0).slice(0, perDoc);
    for (const f of tables) {
      const n = Number(f.match(/(\d+)/)[1]);
      if (n > pdf.numPages) continue;
      const snippet = clip(fs.readFileSync(path.join(mdDir, name, "pages", f), "utf8"));
      const items = (await (await pdf.getPage(n)).getTextContent()).items.filter((i) => "str" in i);
      const other = n + 3 <= pdf.numPages ? (await (await pdf.getPage(n + 3)).getTextContent()).items.filter((i) => "str" in i) : [];
      const real = locateExcerpt(snippet, items);
      // the control only counts lines that carry a real figure (4+ digits that are not a year, or a decimal): headings and dates ("year ended December 26, 2015") repeat on other pages by nature
      const figureLines = excerptUnits(snippet).filter((u) => u.some(isFigure)).map((u) => u.join(" "));
      const control = other.length && figureLines.length ? locateExcerpt(figureLines.join("\n"), other) : null;
      rows.push({ name, page: n, textItems: items.length, lines: real.lines, found: real.found, control: control ? control.found : null, controlLines: control ? control.lines : 0 });
    }
  }
  const lines = rows.reduce((s, r) => s + r.lines, 0);
  const found = rows.reduce((s, r) => s + r.found, 0);
  const controls = rows.filter((r) => r.control !== null);
  const falseFound = controls.reduce((s, r) => s + r.control, 0);
  const controlLines = controls.reduce((s, r) => s + r.controlLines, 0);
  const noText = rows.filter((r) => r.textItems === 0).length;
  for (const r of rows) console.log(`      ${r.name} p${r.page}: ${r.found}/${r.lines} lines found (${r.textItems} text items); its figure lines on page ${r.page + 3}: ${r.control}/${r.controlLines}`);
  console.log(`REAL  ${rows.length} table pages: ${found}/${lines} excerpt lines located (${((100 * found) / Math.max(1, lines)).toFixed(1)}%); pages with no text layer: ${noText}`);
  console.log(`CTRL  lines with a figure, looked for on another page: ${falseFound}/${controlLines} lines wrongly located (${((100 * falseFound) / Math.max(1, controlLines)).toFixed(1)}%)`);
  check("real pages: at least 80% of excerpt lines are located", () => assert.ok(found / lines >= 0.8, `${((100 * found) / lines).toFixed(1)}%`));
  check("control pages: at most 10% of figure lines are wrongly located", () => assert.ok(controls.length === 0 || falseFound / controlLines <= 0.1, `${((100 * falseFound) / controlLines).toFixed(1)}%`));
}

await realPages();
console.log(failed ? `\n${failed} check(s) FAILED` : "\nall checks passed");
process.exit(failed ? 1 : 0);
