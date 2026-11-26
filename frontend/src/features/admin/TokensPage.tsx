import React from "react";
import { Activity, Coins, Cpu, Users } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useAdminData } from "./AdminLayout";
import { PROMPT, UsageCharts } from "./UsageCharts";
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
  const topUsers = data.top_users ?? [];

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {data.cost && (
          <KpiCard label={k.cost} value={fmt.usd(data.cost.total_usd)} icon={Coins}
                   sub={fill(k.costSub, { p: Math.round(data.cost.estimated_share * 100) })} />
        )}
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
        <CardHeader title={k.chartTitle} subtitle={data.cost ? fill(k.priceNote, { hit: data.cost.prices.hit, miss: data.cost.prices.miss, out: data.cost.prices.out }) : k.costNote} icon={Activity} />
        <UsageCharts series={data.series} tokensOnly />
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card className="min-w-0">
          <CardHeader title={k.byModel} icon={Cpu} />
          {data.by_model.length ? (
            <Table caption={k.byModel} head={[k.colModel, k.colQuestions, k.colTokens, k.colShare, k.colCost]} alignRight={[1, 2, 3, 4]}>
              {data.by_model.map((m) => (
                <tr key={m.model ?? "none"}>
                  <td className={`px-5 py-3 text-fg ${m.model ? "font-mono" : "text-muted"}`}>{m.model ?? k.noModel}</td>
                  <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(m.questions)}</td>
                  <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(m.tokens)}</td>
                  <td className="px-5 py-3 text-right font-mono text-muted">{share(m.tokens)}</td>
                  <td className="px-5 py-3 text-right font-mono text-fg-2">{m.cost_usd != null ? fmt.usd(m.cost_usd) : "—"}</td>
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
            <ol className="divide-y divide-line">
              {topUsers.map((u, i) => {
                const pct = Math.max(2, Math.round((u.tokens / topUsers[0].tokens) * 100));
                return (
                  <li key={u.username ?? "guests"} className="flex items-center gap-4 px-5 py-3">
                    <span className="w-5 font-mono text-xs text-dim">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="truncate text-[13px] font-medium text-fg">{u.username ? `@${u.username}` : p.guest}</span>
                        <span className="font-mono text-xs text-fg-2">
                          {fmt.number(u.tokens)}
                          {u.cost_usd != null && <span className="ml-2 text-muted">{fmt.usd(u.cost_usd)}</span>}
                        </span>
                      </div>
                      <div className="mt-1.5 h-1 rounded-full bg-hover" aria-hidden>
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: PROMPT }} />
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

      <Card className="min-w-0">
        <CardHeader title={k.byPurpose} subtitle={k.byPurposeNote} icon={Activity} />
        {data.by_purpose?.length ? (
          <Table caption={k.byPurpose} head={[k.colPurpose, k.colCalls, k.colSeconds, k.colTokens, k.colShare, k.colCost]} alignRight={[1, 2, 3, 4, 5]}>
            {data.by_purpose.map((r) => (
              <tr key={r.purpose}>
                <td className="px-5 py-3 text-fg">{p.steps.purposes[r.purpose] ?? r.purpose}</td>
                <td className="px-5 py-3 text-right font-mono text-fg-2">
                  {fmt.number(r.calls)}
                  {r.failed > 0 && <span className="ml-1 text-xs text-muted">{fill(k.failed, { n: r.failed })}</span>}
                </td>
                <td className="px-5 py-3 text-right font-mono text-fg-2">{`${r.seconds_p50} / ${r.seconds_p90}`}</td>
                <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(r.tokens)}</td>
                <td className="px-5 py-3 text-right font-mono text-muted">{`${Math.round(r.share * 100)}%`}</td>
                <td className="px-5 py-3 text-right font-mono text-fg-2">{r.cost_usd != null ? fmt.usd(r.cost_usd) : "—"}</td>
              </tr>
            ))}
          </Table>
        ) : (
          <EmptyState title={p.chart.empty} />
        )}
      </Card>
    </>
  );
};
