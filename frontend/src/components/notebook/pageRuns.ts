/** A range of consecutive pages, e.g. 6–9. */
export interface PageRun {
  first: number;
  last: number;
}

/** The pages to check, as the document card lists them: sorted, each run of consecutive pages as one range, at most `max` ranges (`more` = the rest). */
export const pageRuns = (pages: number[] | undefined, max = 8): { runs: PageRun[]; more: number } => {
  const sorted = [...new Set(pages ?? [])].sort((a, b) => a - b);
  const runs: PageRun[] = [];
  for (const page of sorted) {
    const last = runs[runs.length - 1];
    if (last && page === last.last + 1) last.last = page;
    else runs.push({ first: page, last: page });
  }
  return { runs: runs.slice(0, max), more: Math.max(0, runs.length - max) };
};
