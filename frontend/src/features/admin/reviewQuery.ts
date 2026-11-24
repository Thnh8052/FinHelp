import type { FlaggedPage, PageFlag, ReviewLabel, ReviewStatus } from "./types";

/** The cited pages read with a problem at upload, as one line: "FinStats.pdf p. 50 (table may be misread) · ..." (owner 25/11). */
export const flaggedPagesText = (pages: FlaggedPage[], w: { pageOf: string; deletedDocument: string; pageFlags: Record<PageFlag, string> }): string =>
  pages
    .map((p) => `${w.pageOf.replace("{file}", p.file_name ?? w.deletedDocument).replace("{page}", String(p.page))} (${p.flags.map((f) => w.pageFlags[f]).join(", ")})`)
    .join(" · ");

/** GET path of the review queue for the page's filters ("" = every user / every problem). */
export const reviewPath = (f: { days: number; user: string; label: ReviewLabel | ""; status: ReviewStatus }): string => {
  const q = new URLSearchParams({ days: String(f.days), status: f.status });
  if (f.label) q.set("label", f.label);
  if (f.user) q.set("user", f.user);
  return `/auth/admin/review?${q.toString()}`;
};

export type LabelTone = "negative" | "warn" | "neutral";

/** How loud a problem label is: a user's report or a blocked answer is red; an answer that may be wrong or incomplete amber; slowness neutral. */
export const labelTone = (label: ReviewLabel): LabelTone =>
  label === "user_report" || label === "blocked" ? "negative" : ["not_traced", "partial", "not_found", "refused"].includes(label) ? "warn" : "neutral";
