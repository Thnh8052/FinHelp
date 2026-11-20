/** The numbers an answer's citations are shown with. The model writes [n] with n the position of the excerpt it was sent, so an answer that uses two
 * of nine excerpts says [1] and [5] and its source list jumped from 1 to 5 (production check 20/11). Here they are shown as 1, 2, 3 in the order
 * the text meets them; the excerpt behind each number, and the figures looked up for the PDF, still use the original number. */
const CITE = /\[(\d+)\]/g;

/** original number -> shown number: every [n] of the text in order of first appearance, then the cited excerpts the text never names (so each card has
 * a number, and no two excerpts share one). */
export function displayNumbers(content: string, cited: number[]): Map<number, number> {
  const numbers = new Map<number, number>();
  const add = (n: number) => {
    if (!numbers.has(n)) numbers.set(n, numbers.size + 1);
  };
  for (const m of content.matchAll(CITE)) add(parseInt(m[1], 10));
  for (const n of cited) add(n);
  return numbers;
}

/** The text with every [n] rewritten to its shown number (one pass, so 1 -> 2 is never read again as 2 -> 3). */
export function renumber(content: string, numbers: Map<number, number>): string {
  return content.replace(CITE, (all, n: string) => {
    const shown = numbers.get(parseInt(n, 10));
    return shown === undefined ? all : `[${shown}]`;
  });
}
