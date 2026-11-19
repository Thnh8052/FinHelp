import type { ReviewLabel, ReviewStatus } from "./types";

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
  label === "user_report" || label === "blocked" ? "negative" : ["warning", "not_traced", "partial", "not_found", "refused"].includes(label) ? "warn" : "neutral";
