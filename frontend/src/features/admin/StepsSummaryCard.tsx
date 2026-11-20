import React, { useEffect, useState } from "react";
import { Layers } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { apiRequest } from "../../services/api";
import { useAdminData } from "./AdminLayout";
import { codeText, rate, summaryPath, summaryRows } from "./stepsView";
import type { StepName, StepsSummary } from "./stepsView";
import { Card, CardHeader, Skeleton, fill, useFormat } from "./ui";

const ORDER: StepName[] = ["gate", "input", "guard", "scope", "plan", "search", "write", "check", "buttons"];

/** The steps of the newest answers added up (backend admin/steps_summary.py): where questions stop, seconds per step, what the guard decided, how often "Search deeper" is used. */
export const StepsSummaryCard: React.FC = () => {
  const { days, user } = useAdminData();
  const { t } = useLanguage();
  const s = t.adminPanel.stepsSummary;
  const names = t.adminPanel.steps;
  const fmt = useFormat();
  const [data, setData] = useState<StepsSummary | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setFailed(false);
    apiRequest<StepsSummary>(summaryPath(days, user))
      .then((d) => live && setData(d))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [days, user]);

  const rows = data ? summaryRows(data, ORDER) : [];
  const guardLabels = data ? Object.entries(data.guard.labels).sort((a, b) => b[1] - a[1]) : [];
  return (
    <Card>
      <CardHeader title={s.title} subtitle={data ? fill(s.note, { n: fmt.number(data.questions), days }) : undefined} icon={Layers} />
      {failed ? (
        <p role="alert" className="px-5 py-4 text-sm text-negative-text">
          {s.failed}
        </p>
      ) : !data ? (
        <Skeleton className="m-5 h-40" />
      ) : data.questions === 0 ? (
        <p className="px-5 py-4 text-sm text-muted">{s.empty}</p>
      ) : (
        <div className="grid gap-5 px-5 py-4 text-[13px] text-fg-2 lg:grid-cols-2">
          <div className="min-w-0">
            <p className="mb-2 text-xs text-dim">{fill(s.questions, { questions: fmt.number(data.questions), answered: fmt.number(data.answered) })}</p>
            <table className="w-full text-left">
              <thead className="text-xs text-dim">
                <tr>
                  <th className="py-1 font-medium">{s.step}</th>
                  <th className="py-1 text-right font-medium">{s.stoppedHere}</th>
                  <th className="py-1 text-right font-medium">{s.median}</th>
                  <th className="py-1 text-right font-medium">{s.p90}</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows.map((r) => (
                  <tr key={r.step} className="border-t border-line">
                    <td className="py-1 font-sans text-fg">{names.names[r.step]}</td>
                    <td className="py-1 text-right">{r.stopped || "–"}</td>
                    <td className="py-1 text-right">{r.p50 ?? "–"}</td>
                    <td className="py-1 text-right">{r.p90 ?? "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="grid min-w-0 content-start gap-3">
            <div>
              <p className="font-medium text-fg">{s.guardTitle}</p>
              <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                {guardLabels.map(([label, n]) => (
                  <li key={label}>
                    {codeText(names.codes, "guard", label)} <span className="font-mono text-dim">{n}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-1 text-muted">{fill(s.guardWait, { over: data.guard.waited.over_half_second, n: data.guard.waited.answers })}</p>
            </div>
            {Object.keys(data.degraded).length > 0 && (
              <div>
                <p className="font-medium text-fg">{s.degradedTitle}</p>
                <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
                  {Object.entries(data.degraded).map(([code, n]) => (
                    <li key={code}>
                      {names.codes.reasons[code] ?? code} <span className="font-mono text-dim">{n}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <p className="font-medium text-fg">{s.deeperTitle}</p>
              <p className="mt-1 text-muted">
                {fill(s.deeperLine, {
                  offered: data.search_deeper.offered,
                  prominent: data.search_deeper.prominent,
                  clicks: data.search_deeper.clicks,
                  share: rate(data.search_deeper.clicks, data.search_deeper.offered),
                })}
              </p>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
