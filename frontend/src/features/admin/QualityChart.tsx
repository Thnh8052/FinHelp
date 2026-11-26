import React, { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipProps } from "recharts";
import { BarChart3, Table2 } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import type { DayQuality } from "./types";
import { EmptyState, useFormat } from "./ui";

/* Categorical slots 1-4 of the chart palette, the same hex on both themes like UsageCharts; validated 26/11/2026 with the dataviz validator
   on the dark and the light --bg-card surfaces: all checks pass (worst adjacent CVD ΔE 8.4, every colour >= 3:1). */
const COLORS = { missing: "#3987e5", refused: "#d95926", not_traced: "#199e70", user_report: "#c98500" } as const; // theme-ok
type Key = keyof typeof COLORS;
const GRID = "var(--border-subtle)";
const AXIS = "var(--text-dim)";

interface Row {
  date: string;
  label: string;
  answers: number;
  missing: number;
  refused: number;
  not_traced: number;
  user_report: number;
  needs_fix: number;
  reviewed_ok: number;
}

const QualityTooltip: React.FC<TooltipProps<number, string> & { names: Record<string, string>; answersLabel: string }> = ({
  active, payload, label, names, answersLabel,
}) => {
  const fmt = useFormat();
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Row;
  return (
    <div className="rounded-lg border border-line-strong bg-panel px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-fg">{label} · {fill1(answersLabel, row.answers)}</div>
      {payload.map((item) => (
        <div key={String(item.dataKey)} className="flex items-center gap-2 text-fg-2">
          <span className="size-2 rounded-sm" style={{ background: item.color }} aria-hidden />
          <span className="flex-1">{names[String(item.dataKey)]}</span>
          <span className="font-mono text-fg">{fmt.number(Number(item.value))}</span>
        </div>
      ))}
    </div>
  );
};

const fill1 = (template: string, n: number) => template.replace("{n}", String(n));

/** The answers with a problem per day, grouped like the review queue's labels (plan 26/11/2026 3.4), with a table view. */
export const QualityChart: React.FC<{ quality: DayQuality[] }> = ({ quality }) => {
  const { t } = useLanguage();
  const c = t.adminPanel.chart;
  const q = t.adminPanel.quality;
  const fmt = useFormat();
  const [asTable, setAsTable] = useState(false);
  const rows: Row[] = quality.map((d) => ({
    date: d.date, label: fmt.day(d.date), answers: d.answers, missing: d.not_found + d.partial, refused: d.refused + d.safety + d.blocked,
    not_traced: d.not_traced, user_report: d.user_report, needs_fix: d.needs_fix, reviewed_ok: d.reviewed_ok,
  }));
  const names: Record<Key, string> = { missing: q.missing, refused: q.refused, not_traced: q.notTraced, user_report: q.userReport };
  const order: Key[] = ["missing", "refused", "not_traced", "user_report"];

  if (!rows.some((r) => r.answers > 0)) return <EmptyState title={c.empty} />;

  const axisProps = { stroke: AXIS, fontSize: 11, tickLine: false, axisLine: false } as const;
  const toggle = (
    <button
      type="button"
      onClick={() => setAsTable((v) => !v)}
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium text-muted hover:bg-hover hover:text-fg"
    >
      {asTable ? <BarChart3 size={14} aria-hidden /> : <Table2 size={14} aria-hidden />}
      {asTable ? c.chartToggle : c.tableToggle}
    </button>
  );

  if (asTable) {
    return (
      <div className="flex flex-col gap-3 p-5">
        <div className="flex justify-end">{toggle}</div>
        <div className="max-h-80 overflow-auto">
          <table className="w-full text-[13px]">
            <caption className="sr-only">{q.title}</caption>
            <thead className="sticky top-0 bg-card text-xs uppercase tracking-wide text-dim">
              <tr>
                <th scope="col" className="py-2 text-left font-medium">{c.date}</th>
                <th scope="col" className="py-2 text-right font-medium">{q.answers}</th>
                {order.map((k) => (
                  <th key={k} scope="col" className="py-2 text-right font-medium">{names[k]}</th>
                ))}
                <th scope="col" className="py-2 text-right font-medium">{q.needsFix}</th>
                <th scope="col" className="py-2 text-right font-medium">{q.reviewedOk}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line font-mono text-fg-2">
              {rows.map((r) => (
                <tr key={r.date}>
                  <td className="py-1.5">{r.label}</td>
                  <td className="py-1.5 text-right">{fmt.number(r.answers)}</td>
                  {order.map((k) => (
                    <td key={k} className="py-1.5 text-right">{fmt.number(r[k])}</td>
                  ))}
                  <td className="py-1.5 text-right">{fmt.number(r.needs_fix)}</td>
                  <td className="py-1.5 text-right">{fmt.number(r.reviewed_ok)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-wrap items-center justify-end gap-4">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {order.map((k) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: COLORS[k] }} aria-hidden />
              {names[k]}
            </li>
          ))}
        </ul>
        {toggle}
      </div>
      <div className="h-52" role="img" aria-label={q.aria}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barCategoryGap="25%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" {...axisProps} minTickGap={16} />
            <YAxis {...axisProps} width={44} allowDecimals={false} />
            <Tooltip cursor={{ fill: "var(--bg-hover)" }} content={<QualityTooltip names={names} answersLabel={q.answersOfDay} />} />
            {order.map((k, i) => (
              <Bar key={k} dataKey={k} stackId="q" fill={COLORS[k]} stroke="var(--bg-card)" strokeWidth={2}
                   radius={i === order.length - 1 ? [4, 4, 0, 0] : undefined} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
