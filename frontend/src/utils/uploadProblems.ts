/** What a batch of files left out is told to the user: one message, not the last of several (production check 20/11: three rejected files showed one toast). */
export interface UploadProblem {
  message: string;
  level: "warning" | "error";
  actionLabel?: string;
  onAction?: () => void;
}

export interface ProblemTexts {
  several: string; // "{n} files were not uploaded:"
  more: string; // "and {n} more"
}

const LISTED = 3;

/** null for no problem; the problem itself for one; for several, one message that lists the first three (each said once) and counts the rest.
 * The worst level wins and the first action (sign in) is kept. */
export function mergeProblems(problems: UploadProblem[], texts: ProblemTexts): UploadProblem | null {
  const unique = problems.filter((p, i) => problems.findIndex((q) => q.message === p.message) === i);
  if (unique.length === 0) return null;
  if (unique.length === 1) return unique[0];
  const rest = unique.length - LISTED;
  const lines = unique.slice(0, LISTED).map((p) => `• ${p.message}`);
  if (rest > 0) lines.push(texts.more.replace("{n}", String(rest)));
  const action = unique.find((p) => p.actionLabel);
  return {
    message: [texts.several.replace("{n}", String(unique.length)), ...lines].join("\n"),
    level: unique.some((p) => p.level === "error") ? "error" : "warning",
    ...(action ? { actionLabel: action.actionLabel, onAction: action.onAction } : {}),
  };
}
