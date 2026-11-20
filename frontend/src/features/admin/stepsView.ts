/** GET /auth/admin/steps/{message_id} (backend/app/modules/admin/steps.py): what the system did for one answer, step by step, read from its stored trace. */
export type StepOutcome = "ok" | "warn" | "stopped" | "skipped";
export type StepName = "gate" | "input" | "guard" | "scope" | "plan" | "search" | "write" | "check" | "buttons";

export interface AnswerStep {
  step: StepName;
  outcome: StepOutcome;
  code: string | null; // the decision of the step: the guard's label, the input rule's action, the rule that chose the documents...
  seconds: number | null;
  facts: Record<string, unknown>; // a few short values and counts
}

export interface ModelCall {
  purpose: string;
  seconds?: number;
  attempts?: number;
  status?: string;
  first_piece_seconds?: number;
  thinking?: boolean;
  prompt_tokens?: number;
  completion_tokens?: number;
  reasoning_tokens?: number;
  prompt_cache_hit_tokens?: number;
}

export interface AnswerSteps {
  message_id: string;
  latency_ms: number | null;
  steps: AnswerStep[];
  stopped_at: StepName | null;
  total_seconds: number | null;
  calls: ModelCall[];
}

export const stepsPath = (messageId: string): string => `/auth/admin/steps/${encodeURIComponent(messageId)}`;

/** Label and value of each fact, in the order the server sent them. A key with no label shows its own name; a list is joined; a code, alone or in a list, is said in words when
 * `words` has them (the reasons of a button, the steps dropped for time, the guard's result); a true flag is a tick. */
export function describeFacts(facts: Record<string, unknown>, names: Record<string, string>, words: Record<string, string> = {}): Array<[string, string]> {
  return Object.entries(facts).map(([key, value]) => {
    const said = (v: unknown) => words[String(v)] ?? String(v);
    const text = Array.isArray(value) ? value.map(said).join(", ") : value === true ? "✓" : key.endsWith("_seconds") ? `${value} s` : said(value);
    return [names[key] ?? key, text];
  });
}

/** The words for a decision code of a step; an unknown code shows as it is, no code shows nothing. */
export function codeText(codes: Record<string, Record<string, string>>, step: string, code: string | null): string {
  return code ? codes[step]?.[code] ?? code : "";
}

export const outcomeTone = (outcome: StepOutcome): "neutral" | "warn" | "negative" => (outcome === "warn" ? "warn" : outcome === "stopped" ? "negative" : "neutral");

/** GET /auth/admin/steps-summary (backend admin/steps_summary.py): the steps of many answers added up. */
export interface StepsSummary {
  window_days: number;
  questions: number;
  answered: number;
  stopped: Record<string, number>;
  seconds: Record<string, { n: number; p50: number; p90: number }>;
  guard: { labels: Record<string, number>; outcomes: Record<string, number>; waited: { answers: number; over_half_second: number } };
  degraded: Record<string, number>;
  search_deeper: { offered: number; prominent: number; clicks: number };
}

export const summaryPath = (days: number, user: string): string => `/auth/admin/steps-summary?days=${days}${user ? `&user=${encodeURIComponent(user)}` : ""}`;

export interface SummaryRow {
  step: StepName;
  stopped: number;
  n: number | null;
  p50: number | null;
  p90: number | null;
}

/** One row per step in the order given: how many questions stopped there and the median and p90 seconds of the step (null where it has no time of its own). */
export function summaryRows(summary: StepsSummary, order: StepName[]): SummaryRow[] {
  return order.map((step) => {
    const s = summary.seconds[step];
    return { step, stopped: summary.stopped[step] ?? 0, n: s?.n ?? null, p50: s?.p50 ?? null, p90: s?.p90 ?? null };
  });
}

/** A share as a whole percent, or a dash when there is nothing to divide. */
export const rate = (part: number, whole: number): string => (whole > 0 ? `${Math.round((100 * part) / whole)} %` : "–");
