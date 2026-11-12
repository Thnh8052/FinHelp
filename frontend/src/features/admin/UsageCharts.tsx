import React, { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TooltipProps } from "recharts";
import { BarChart3, Table2 } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import type { DayUsage } from "./types";
import { EmptyState, useFormat } from "./ui";

/* Validated with the dataviz palette checker on the card surface #0e1526 (dark): CVD ΔE 19.6, both >= 3:1 */
const PROMPT = "#3987e5";
const COMPLETION = "#199e70";
const GRID = "rgba(255,255,255,0.06)";
const AXIS = "#8291a8";

interface Row extends DayUsage {
  label: string;
}

const ChartTooltip: React.FC<TooltipProps<number, string> & { names: Record<string, string> }> = ({ active, payload, label, names }) => {
  const fmt = useFormat();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line-strong bg-panel px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-fg">{label}</div>
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

const Legend: React.FC<{ items: { color: string; label: string }[] }> = ({ items }) => (
  <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
    {items.map((i) => (
      <li key={i.label} className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm" style={{ background: i.color }} aria-hidden />
        {i.label}
      </li>
    ))}
  </ul>
);

/** Questions and tokens per day as two charts on one time axis: their scales differ by thousands, so never one chart with two y-axes. */
export const UsageCharts: React.FC<{ series: DayUsage[]; tokensOnly?: boolean }> = ({ series, tokensOnly = false }) => {
  const { t } = useLanguage();
  const c = t.adminPanel.chart;
  const fmt = useFormat();
  const [asTable, setAsTable] = useState(false);
  const rows: Row[] = series.map((d) => ({ ...d, label: fmt.day(d.date) }));
  const names = { questions: c.questions, prompt_tokens: c.prompt, completion_tokens: c.completion };

  if (!series.some((d) => d.questions > 0)) return <EmptyState title={c.empty} />;

  const axisProps = { stroke: AXIS, fontSize: 11, tickLine: false, axisLine: false } as const;
  const toggle = (
    <button
      type="button"
      onClick={() => setAsTable((v) => !v)}
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs font-medium text-muted hover:bg-white/5 hover:text-fg"
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
            <caption className="sr-only">{c.title}</caption>
            <thead className="sticky top-0 bg-card text-xs uppercase tracking-wide text-dim">
              <tr>
                <th scope="col" className="py-2 text-left font-medium">{c.date}</th>
                {!tokensOnly && <th scope="col" className="py-2 text-right font-medium">{c.questions}</th>}
                <th scope="col" className="py-2 text-right font-medium">{c.prompt}</th>
                <th scope="col" className="py-2 text-right font-medium">{c.completion}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-mono text-fg-2">
              {rows.map((r) => (
                <tr key={r.date}>
                  <td className="py-1.5">{r.label}</td>
                  {!tokensOnly && <td className="py-1.5 text-right">{fmt.number(r.questions)}</td>}
                  <td className="py-1.5 text-right">{fmt.number(r.prompt_tokens)}</td>
                  <td className="py-1.5 text-right">{fmt.number(r.completion_tokens)}</td>
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[13px] font-semibold text-fg-2">{c.tokens}</h3>
        <div className="flex flex-wrap items-center gap-4">
          <Legend items={[{ color: PROMPT, label: c.prompt }, { color: COMPLETION, label: c.completion }]} />
          {toggle}
        </div>
      </div>
      <div className={tokensOnly ? "h-72" : "h-52"} role="img" aria-label={c.tokensAria}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barCategoryGap="25%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" {...axisProps} minTickGap={16} />
            <YAxis {...axisProps} width={44} tickFormatter={(v: number) => fmt.compact(v)} />
            <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<ChartTooltip names={names} />} />
            <Bar dataKey="prompt_tokens" stackId="t" fill={PROMPT} stroke="#0e1526" strokeWidth={1} />
            <Bar dataKey="completion_tokens" stackId="t" fill={COMPLETION} stroke="#0e1526" strokeWidth={1} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {!tokensOnly && (
        <>
          <h3 className="text-[13px] font-semibold text-fg-2">{c.questions}</h3>
          <div className="h-36" role="img" aria-label={c.questionsAria}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }} barCategoryGap="25%">
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="label" {...axisProps} minTickGap={16} />
                <YAxis {...axisProps} width={44} allowDecimals={false} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)" }} content={<ChartTooltip names={names} />} />
                <Bar dataKey="questions" fill={PROMPT} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
};
