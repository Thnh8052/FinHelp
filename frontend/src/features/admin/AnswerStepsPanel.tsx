import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { apiRequest } from "../../services/api";
import { codeText, describeFacts, outcomeTone, stepsPath } from "./stepsView";
import type { AnswerSteps } from "./stepsView";
import { fill } from "./ui";

const TONE = { negative: "bg-negative-soft text-negative-text", warn: "bg-warn/15 text-warn-text", neutral: "bg-hover text-fg-2" } as const;

/** What the system did for one answer, step by step (backend admin/steps.py). Read when opened, not with the list: a list of 200 answers stays light. */
export const AnswerStepsPanel: React.FC<{ messageId: string }> = ({ messageId }) => {
  const { t } = useLanguage();
  const s = t.adminPanel.steps;
  const [data, setData] = useState<AnswerSteps | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "failed">("idle");

  const load = async () => {
    if (data || state === "loading") return;
    setState("loading");
    try {
      setData(await apiRequest<AnswerSteps>(stepsPath(messageId)));
      setState("idle");
    } catch {
      setState("failed");
    }
  };

  return (
    <details className="mt-2" onToggle={(e) => e.currentTarget.open && void load()}>
      <summary className="cursor-pointer text-xs font-medium text-muted hover:text-fg">{s.title}</summary>
      <div className="mt-2 rounded-lg border border-line px-3 py-2.5 text-[12.5px] text-fg-2">
        {state === "loading" && <p className="text-muted">{s.loading}</p>}
        {state === "failed" && (
          <p role="alert" className="text-negative-text">
            {s.failed}
          </p>
        )}
        {data && !data.steps.length && <p className="text-muted">{s.none}</p>}
        {data && data.steps.length > 0 && (
          <>
            <ol className="grid gap-2.5">
              {data.steps.map((step) => {
                const facts = describeFacts(step.facts, s.facts);
                return (
                  <li key={step.step}>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className={`rounded-md px-1.5 py-0.5 text-[11.5px] font-medium ${TONE[outcomeTone(step.outcome)]}`}>{s.outcomes[step.outcome]}</span>
                      <span className="font-medium text-fg">{s.names[step.step]}</span>
                      {step.code && <span>{codeText(s.codes, step.step, step.code)}</span>}
                      {step.seconds != null && <span className="ml-auto font-mono text-xs text-dim">{step.seconds} s</span>}
                    </div>
                    {facts.length > 0 && (
                      <dl className="mt-0.5 grid gap-0.5 pl-1 text-muted">
                        {facts.map(([label, value]) => (
                          <div key={label} className="break-words">
                            <dt className="inline">{label}: </dt>
                            <dd className="inline">{value}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                  </li>
                );
              })}
            </ol>
            <p className="mt-2.5 text-xs text-dim">
              {data.stopped_at && <span className="mr-3 font-medium text-negative-text">{fill(s.stoppedAt, { step: s.names[data.stopped_at] })}</span>}
              {data.total_seconds != null && fill(s.total, { s: data.total_seconds })}
            </p>
            {data.calls.length > 0 && (
              <div className="mt-2">
                <p className="font-medium text-fg">{s.calls}</p>
                <ul className="mt-0.5 grid gap-0.5 font-mono text-xs text-muted">
                  {data.calls.map((c, i) => (
                    <li key={i}>
                      {fill(s.callLine, { purpose: s.purposes[c.purpose] ?? c.purpose, s: c.seconds ?? "-", status: c.status ?? "-" })}
                      {c.prompt_tokens != null && ` · ${fill(s.tokens, { in: c.prompt_tokens, out: c.completion_tokens ?? 0, think: c.reasoning_tokens ?? 0 })}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
};
