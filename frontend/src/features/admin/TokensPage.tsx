import React from "react";
import { Activity, Coins, Cpu, Users } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useAdminData } from "./AdminLayout";
import { UsageCharts } from "./UsageCharts";
import { Card, CardHeader, EmptyState, KpiCard, Skeleton, Table, fill, useFormat } from "./ui";

export const TokensPage: React.FC = () => {
  const { data, loading } = useAdminData();
  const { t } = useLanguage();
  const p = t.adminPanel;
  const k = p.tokens;
  const fmt = useFormat();

  if (!data) return loading ? <Skeleton className="h-96" /> : null;

  const prompt = data.series.reduce((s, d) => s + d.prompt_tokens, 0);
  const completion = data.series.reduce((s, d) => s + d.completion_tokens, 0);
  const total = prompt + completion;
  const share = (n: number) => (total ? `${Math.round((n / total) * 100)}%` : "—");
  const topUsers = data.users.filter((u) => u.total_tokens > 0).slice(0, 8);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label={k.total} value={fmt.compact(total)} icon={Coins} sub={fill(p.kpi.inDays, { n: data.window_days })} />
        <KpiCard label={k.prompt} value={fmt.compact(prompt)} icon={Coins} sub={fill(k.share, { p: share(prompt) })} />
        <KpiCard label={k.completion} value={fmt.compact(completion)} icon={Coins} sub={fill(k.share, { p: share(completion) })} />
        <KpiCard
          label={k.perQuestion}
          value={data.totals.current.questions ? fmt.number(Math.round(total / data.totals.current.questions)) : "—"}
          icon={Activity}
          sub={fill(k.overQuestions, { n: data.totals.current.questions })}
        />
      </div>

      <Card>
        <CardHeader title={k.chartTitle} subtitle={k.costNote} icon={Activity} />
        <UsageCharts series={data.series} tokensOnly />
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader title={k.byModel} icon={Cpu} />
          {data.by_model.length ? (
            <Table caption={k.byModel} head={[k.colModel, k.colQuestions, k.colTokens, k.colShare]} alignRight={[1, 2, 3]}>
              {data.by_model.map((m) => (
                <tr key={m.model}>
                  <td className="px-5 py-3 font-mono text-fg">{m.model}</td>
                  <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(m.questions)}</td>
                  <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(m.tokens)}</td>
                  <td className="px-5 py-3 text-right font-mono text-muted">{share(m.tokens)}</td>
                </tr>
              ))}
            </Table>
          ) : (
            <EmptyState title={p.chart.empty} />
          )}
        </Card>
        <Card className="min-w-0">
          <CardHeader title={k.topUsers} subtitle={k.topUsersNote} icon={Users} />
          {topUsers.length ? (
            <ol className="divide-y divide-white/5">
              {topUsers.map((u, i) => {
                const pct = Math.max(2, Math.round((u.total_tokens / topUsers[0].total_tokens) * 100));
                return (
                  <li key={u.user_id} className="flex items-center gap-4 px-5 py-3">
                    <span className="w-5 font-mono text-xs text-dim">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-[13px] font-medium text-fg">@{u.username}</span>
                        <span className="font-mono text-xs text-fg-2">{fmt.number(u.total_tokens)}</span>
                      </div>
                      <div className="mt-1.5 h-1 rounded-full bg-white/5" aria-hidden>
                        <div className="h-full rounded-full bg-[#3987e5]" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <EmptyState title={p.users.noTokens} />
          )}
        </Card>
      </div>
    </>
  );
};
