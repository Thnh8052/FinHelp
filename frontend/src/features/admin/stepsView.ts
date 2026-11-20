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

/** Label and value of each fact, in the order the server sent them. A key with no label shows its own name; a list is joined; a true flag is a tick. */
export function describeFacts(facts: Record<string, unknown>, names: Record<string, string>): Array<[string, string]> {
  return Object.entries(facts).map(([key, value]) => {
    const text = Array.isArray(value) ? value.join(", ") : value === true ? "✓" : key.endsWith("_seconds") ? `${value} s` : String(value);
    return [names[key] ?? key, text];
  });
}

/** The words for a decision code of a step; an unknown code shows as it is, no code shows nothing. */
export function codeText(codes: Record<string, Record<string, string>>, step: string, code: string | null): string {
  return code ? codes[step]?.[code] ?? code : "";
}

export const outcomeTone = (outcome: StepOutcome): "neutral" | "warn" | "negative" => (outcome === "warn" ? "warn" : outcome === "stopped" ? "negative" : "neutral");
