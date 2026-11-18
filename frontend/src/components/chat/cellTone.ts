// How a table cell of an answer is classified. Pure functions, tested by scripts/test-cell-tone.mjs.

/** A cell that holds only a figure and its citations: "177,866 [5]", "+30.9%", "(1,204) [2][3]", "$ (5)". */
const NUMERIC_CELL = /^[+\-−–$€£(\s]*\d[\d.,\s]*(?:%|x|X)?\)?(?:\s*\[\d+\])*$/;

/** A cell with nothing in it: a dash, or "N/A". */
const EMPTY_CELL = /^(?:[—–−-]|n\/a)$/i;

/** A header title this long needs a wider column: squeezed into a narrow one it becomes a tall strip of short lines. */
export const isLongHeader = (title: string): boolean => title.trim().length > 24;

export const isNumericCell =(text: string): boolean => NUMERIC_CELL.test(text.trim());

/**
 * The colour of a cell: only a signed figure is coloured. A plus sign is a rise, a minus sign or brackets (as in accounts) a fall.
 * A margin, a share, a label and any other text stay plain: a "%" alone says nothing about growth.
 */
export function cellTone(text: string): "positive" | "negative" | "empty" | "" {
  const t = text.trim();
  if (EMPTY_CELL.test(t)) return "empty";
  if (!NUMERIC_CELL.test(t)) return "";
  const figure = t.replace(/^[$€£\s]+/, "");
  if (figure.startsWith("(") || /^[−–-]/.test(figure)) return "negative";
  return figure.startsWith("+") ? "positive" : "";
}
