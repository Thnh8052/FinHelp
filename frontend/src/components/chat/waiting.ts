import type { ChatStage } from "../../types/chat";

/** The four steps of the stage bar. "analyzing" (the model's first reasoning piece arrived, T6a) is part of the writing step: it has no step of its own. */
export const STAGES: ChatStage[] = ["understanding", "searching", "writing", "checking"];

export const barIndex = (stage: ChatStage): number => STAGES.indexOf(stage === "analyzing" ? "writing" : stage);

export interface WaitingTexts {
  stages: Record<ChatStage, string>; // "analyzing" carries {s}: the seconds since the model started thinking
  slow: string;
  click: Record<string, string>;
}

/** The line under the spinner while an answer is awaited. A stage that lasts long says so, except "analyzing": its clock already shows nothing hung. After a click,
 * the two search stages say what the click does. */
export function waitingText(o: { stage: ChatStage; slow: boolean; click: string; seconds: number; texts: WaitingTexts }): string {
  const { stage, slow, click, seconds, texts } = o;
  if (stage === "analyzing") return texts.stages.analyzing.replace("{s}", String(seconds));
  if (slow) return texts.slow;
  if (click && (stage === "understanding" || stage === "searching")) return texts.click[click] ?? texts.stages[stage];
  return texts.stages[stage];
}
