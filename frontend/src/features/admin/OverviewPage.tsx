import React from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowRight, Coins, FileText, Flag, MessageSquareText } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useAdminData } from "./AdminLayout";
import { AnswerList } from "./AuditPage";
import { DocumentsTable } from "./DocumentsPage";
import { UsageCharts } from "./UsageCharts";
import type { AdminOverview } from "./types";
import { Card, CardHeader, KpiCard, Skeleton, fill, useFormat } from "./ui";

/** Change vs the previous window of the same length; null when that window had nothing to compare with. */
const change = (now: number, before: number) => (before > 0 ? (now - before) / before : null);

const ViewAll: React.FC<{ to: string; label: string }> = ({ to, label }) => (
  <Link to={to} className="inline-flex items-center gap-1 text-[13px] font-medium text-blue-400 hover:text-blue-300">
    {label}
    <ArrowRight size={14} aria-hidden />
  </Link>
);

const ServiceHealth: React.FC<{ services: AdminOverview["services"] }> = ({ services }) => {
  const { t } = useLanguage();
  const h = t.adminPanel.health;
  return (
    <ul className="flex flex-wrap gap-2" aria-label={h.title}>
      {Object.entries(services).map(([name, ms]) => (
        <li
          key={name}
          className="inline-flex items-center gap-2 rounded-lg border border-line bg-card px-3 py-1.5 text-xs text-fg-2"
        >
          <span className={`size-2 rounded-full ${ms != null ? "bg-emerald-400" : "bg-rose-400"}`} aria-hidden />
          <span className="font-medium">{h.names[name as keyof typeof h.names] ?? name}</span>
          <span className={ms != null ? "font-mono text-muted" : "text-rose-300"}>
            {ms != null ? fill(h.up, { ms: Math.round(ms) }) : h.down}
          </span>
        </li>
      ))}
    </ul>
  );
};

export const OverviewPage: React.FC = () => {
  const { data, loading } = useAdminData();
  const { t } = useLanguage();
  const p = t.adminPanel;
  const fmt = useFormat();

  if (!data) {
    return loading ? (
      <div className="flex flex-col gap-6" aria-label={t.common.loading}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    ) : null;
  }

  const { current, previous, documents } = data.totals;
  const days = data.window_days;
  const docsInFlight = data.documents.filter((d) => d.status !== "ready");

  return (
    <>
      <ServiceHealth services={data.services} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label={p.kpi.questions}
          value={fmt.number(current.questions)}
          icon={MessageSquareText}
          change={change(current.questions, previous.questions)}
          sub={current.avg_latency_ms != null ? fill(p.kpi.avgLatency, { s: fmt.seconds(current.avg_latency_ms) }) : fill(p.kpi.inDays, { n: days })}
        />
        <KpiCard
          label={p.kpi.tokens}
          value={fmt.compact(current.tokens)}
          icon={Coins}
          change={change(current.tokens, previous.tokens)}
          sub={current.questions ? fill(p.kpi.perQuestion, { n: fmt.number(Math.round(current.tokens / current.questions)) }) : fill(p.kpi.inDays, { n: days })}
        />
        <KpiCard
          label={p.kpi.documents}
          value={fmt.number(documents.total)}
          icon={FileText}
          tone={documents.failed ? "warning" : "default"}
          sub={fill(p.kpi.docsSub, { ready: documents.ready, processing: documents.processing, failed: documents.failed })}
        />
        <KpiCard
          label={p.kpi.flagged}
          value={fmt.number(data.totals.flagged_total)}
          icon={Flag}
          tone={data.totals.flagged_total ? "warning" : "default"}
          sub={p.kpi.flaggedSub}
        />
      </div>

      <Card>
        <CardHeader title={p.chart.title} subtitle={fill(p.kpi.inDays, { n: days })} icon={Activity} action={<ViewAll to="/admin/tokens" label={p.nav.tokens} />} />
        <UsageCharts series={data.series} />
      </Card>

      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-5">
        <Card className="min-w-0 2xl:col-span-3">
          <CardHeader
            title={p.docs.title}
            subtitle={docsInFlight.length ? fill(p.docs.inFlight, { n: docsInFlight.length }) : p.docs.allReady}
            icon={FileText}
            action={<ViewAll to="/admin/documents" label={p.viewAll} />}
          />
          {/* What needs attention first (processing, failed), then the newest */}
          <DocumentsTable documents={[...docsInFlight, ...data.documents.filter((d) => d.status === "ready")].slice(0, 6)} emptyText={p.docs.empty} />
        </Card>
        <Card className="min-w-0 2xl:col-span-2">
          <CardHeader title={p.answers.flaggedTitle} subtitle={p.kpi.flaggedSub} icon={Flag} action={<ViewAll to="/admin/audit" label={p.viewAll} />} />
          <AnswerList answers={data.flagged.slice(0, 4)} emptyTitle={p.answers.flaggedEmpty} emptyHint={p.answers.flaggedHint} />
        </Card>
      </div>
    </>
  );
};
