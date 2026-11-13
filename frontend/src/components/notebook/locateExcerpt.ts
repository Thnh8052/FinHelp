/**
 * Finds a cited excerpt on a PDF page, so the viewer can mark the lines the answer was taken from (F9).
 *
 * The excerpt is Markdown written by the parser (a table row is "| Total revenue ..... | $ 4,051,189 | ..."), the page is the list of text items pdf.js reads.
 * The two never match character by character (pipes, dot leaders, "$", thousands separators), so both are cut into words and numbers first,
 * and an excerpt line is looked for as a window of the page's words: the window with the most of the line's words and numbers in it wins.
 * Numbers weigh more than words: they are what tells two rows with the same label apart.
 *
 * Pure functions, no DOM and no pdf.js import, so scripts/test-highlight.mjs can run them on real pages. Type-only syntax, so node can run this file as it is.
 */

/** The part of a pdf.js text item this needs. */
export interface PageItem {
  str: string;
  transform: number[]; // [a, b, c, d, e, f]: text space to page space
  width: number; // page units
}

export interface Box {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Located {
  items: number[]; // indices into the page's items that carry the excerpt
  lines: number; // excerpt lines looked for
  found: number; // of those, lines found on the page
}

const TOKEN = /[A-Za-z]+|\d[\d,]*(?:\.\d+)?/g;
const UNIT_TOKENS = 12; // an excerpt line longer than this (a paragraph) is looked for in pieces of this size
const MIN_UNIT_TOKENS = 2;
const ENOUGH = 0.6; // share of a line's weight that must be inside one window of the page
const NUMBER_WEIGHT = 3;

export function tokenize(text: string): string[] {
  return (text.match(TOKEN) ?? []).map((t) => (/^\d/.test(t) ? t.replace(/,/g, "") : t.toLowerCase()));
}

const weightOf = (t: string) => (/^\d/.test(t) ? NUMBER_WEIGHT : 1);

/** The excerpt as pieces to look for: one per Markdown line (a table row stays whole), long lines cut by word count. */
export function excerptUnits(excerpt: string): string[][] {
  const units: string[][] = [];
  for (const line of excerpt.split("\n")) {
    const tokens = tokenize(line);
    for (let i = 0; i < tokens.length; i += UNIT_TOKENS) {
      const piece = tokens.slice(i, i + UNIT_TOKENS);
      if (piece.length >= MIN_UNIT_TOKENS) units.push(piece);
    }
  }
  return units;
}

interface PageToken {
  t: string;
  item: number;
}

export function pageTokens(items: PageItem[]): PageToken[] {
  const out: PageToken[] = [];
  items.forEach((it, item) => {
    for (const t of tokenize(it.str ?? "")) out.push({ t, item });
  });
  return out;
}

/** Positions (in `page`) of the best window for one line, or null when less than ENOUGH of its weight is anywhere in one window. */
function bestWindow(unit: string[], page: PageToken[]): number[] | null {
  const total = unit.reduce((sum, t) => sum + weightOf(t), 0);
  const span = unit.length * 2 + 6; // a cell or two of other text between the words of a row is normal
  const wanted = new Set(unit);
  let best: number[] | null = null;
  let bestScore = 0;
  for (let start = 0; start < page.length; start++) {
    if (!wanted.has(page[start].t)) continue; // a window starts on a word of the line
    const left = new Map<string, number>();
    for (const t of unit) left.set(t, (left.get(t) ?? 0) + 1);
    const hit: number[] = [];
    let score = 0;
    for (let k = start; k < Math.min(page.length, start + span); k++) {
      const n = left.get(page[k].t);
      if (n) {
        left.set(page[k].t, n - 1);
        hit.push(k);
        score += weightOf(page[k].t);
      }
    }
    // the same score twice: the window where the hits sit closer together (the row, not a label from one row and the figures of the next)
    if (score > bestScore || (score === bestScore && best && hit.length > 1 && hit[hit.length - 1] - hit[0] < best[best.length - 1] - best[0])) {
      bestScore = score;
      best = hit;
    }
  }
  return best && bestScore / total >= ENOUGH && best.length >= MIN_UNIT_TOKENS ? best : null;
}

export function locateExcerpt(excerpt: string, items: PageItem[]): Located {
  const units = excerptUnits(excerpt);
  const page = pageTokens(items);
  const marked = new Set<number>();
  let found = 0;
  for (const unit of units) {
    const hit = bestWindow(unit, page);
    if (!hit) continue;
    found++;
    for (const k of hit) marked.add(page[k].item);
  }
  return { items: [...marked].sort((a, b) => a - b), lines: units.length, found };
}

// ---------------------------------------------------------------- the figures the answer states

/** A number worth looking for on the page: with a thousands separator or decimals, or at least 3 digits, and not a year ("13 weeks", "January 28" and "2023" are noise). */
const isFigure = (raw: string, plain: string) => (raw.includes(",") || raw.includes(".") || plain.length >= 3) && !/^(19|20)\d\d$/.test(plain);

/** The numbers the answer states in the sentences (or lines) that cite [n], without separators: what to look for on the cited page. */
export function citedFigures(answer: string, n: number): string[] {
  const marker = `[${n}]`;
  const figures = new Set<string>();
  const pieces = answer.split(/\n|(?<=[.!?])\s+/).flatMap((piece) => (piece.includes("|") ? piece.split("|") : [piece])); // a table row: one cell at a time
  for (const piece of pieces) {
    if (!piece.includes(marker)) continue;
    for (const raw of piece.replace(/\[\d+\]/g, " ").match(/\d(?:[\d,]*\d)?(?:\.\d+)?/g) ?? []) {
      const plain = raw.replace(/,/g, "");
      if (isFigure(raw, plain)) figures.add(plain);
    }
  }
  return [...figures];
}

/** Items on the same line of text as item `index` (the whole table row, label and figures). */
function sameLine(items: PageItem[], index: number): number[] {
  const y = items[index].transform[5];
  const height = Math.hypot(items[index].transform[2], items[index].transform[3]) || 1;
  const line: number[] = [];
  items.forEach((it, i) => {
    if (it.str?.trim() && Math.abs(it.transform[5] - y) < height * 0.5) line.push(i);
  });
  return line;
}

/** The lines of the page that carry one of the figures (at most `perFigure` places for each, a figure can be printed in the headline and in a table). */
export function figureLines(items: PageItem[], figures: string[], perFigure = 3): number[] {
  const page = pageTokens(items);
  const marked = new Set<number>();
  for (const figure of figures) {
    let places = 0;
    for (const token of page) {
      if (token.t !== figure) continue;
      for (const i of sameLine(items, token.item)) marked.add(i);
      if (++places >= perFigure) break;
    }
  }
  return [...marked].sort((a, b) => a - b);
}

// ---------------------------------------------------------------- where the items are on the drawn page

const multiply = (m: number[], n: number[]): number[] => [
  m[0] * n[0] + m[2] * n[1], m[1] * n[0] + m[3] * n[1],
  m[0] * n[2] + m[2] * n[3], m[1] * n[2] + m[3] * n[3],
  m[0] * n[4] + m[2] * n[5] + m[4], m[1] * n[4] + m[3] * n[5] + m[5],
];

/**
 * One band per line of text: the marked items on the same baseline are joined into one rectangle (a table row is one band, from its label to its last
 * figure), unless a very wide gap separates them (two columns of text). Positions are in CSS pixels on the drawn page.
 * `viewport`: the page's viewport transform as pdf.js gives it (page.getViewport(...).transform) and the page width in the same pixels.
 */
export function bandsFor(items: PageItem[], marked: number[], viewportTransform: number[], pageWidth: number): Box[] {
  const boxes: Box[] = [];
  for (const i of marked) {
    const it = items[i];
    if (!it?.str?.trim()) continue;
    const tx = multiply(viewportTransform, it.transform);
    const height = Math.hypot(tx[2], tx[3]);
    const width = it.width * Math.hypot(viewportTransform[0], viewportTransform[1]);
    if (height <= 0 || width <= 0) continue;
    boxes.push({ left: tx[4], top: tx[5] - height, width, height });
  }
  boxes.sort((a, b) => a.top - b.top || a.left - b.left);
  const maxGap = pageWidth * 0.7; // a table row spans the page; only two far-apart columns stay apart
  const bands: Box[] = [];
  for (const box of boxes) {
    const band = bands.find((b) => Math.abs(b.top + b.height / 2 - (box.top + box.height / 2)) < Math.max(b.height, box.height) * 0.6
      && box.left - (b.left + b.width) < maxGap && b.left - (box.left + box.width) < maxGap);
    if (!band) {
      bands.push({ ...box });
      continue;
    }
    const right = Math.max(band.left + band.width, box.left + box.width);
    const bottom = Math.max(band.top + band.height, box.top + box.height);
    band.left = Math.min(band.left, box.left);
    band.top = Math.min(band.top, box.top);
    band.width = right - band.left;
    band.height = bottom - band.top;
  }
  return bands;
}
