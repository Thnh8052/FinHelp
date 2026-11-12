import React, { useMemo, useState } from "react";
import { FileText } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { processingErrorText } from "../../services/api";
import { useAdminData } from "./AdminLayout";
import type { AdminDocument } from "./types";
import { Card, CardHeader, EmptyState, OwnerLabel, SearchField, Segmented, Skeleton, StatusBadge, Table, fill, useFormat } from "./ui";

export const DocumentsTable: React.FC<{ documents: AdminDocument[]; emptyText: string }> = ({ documents, emptyText }) => {
  const { t } = useLanguage();
  const d = t.adminPanel.docs;
  const fmt = useFormat();
  if (!documents.length) return <EmptyState title={emptyText} icon={FileText} />;

  return (
    <Table caption={d.title} head={[d.colReport, d.colOwner, d.colPages, d.colStatus, d.colDuration, d.colUploaded]} alignRight={[2, 4]}>
      {documents.map((doc) => {
        const stage = doc.stage ? d.stage[doc.stage as keyof typeof d.stage] ?? doc.stage : null;
        const active = doc.status === "processing" || doc.status === "pending";
        const period = [doc.ticker, doc.report_type, doc.fiscal_year && `FY${doc.fiscal_year}`].filter(Boolean).join(" · ");
        return (
          <tr key={doc.document_id} className="align-top transition-colors hover:bg-white/[0.02]">
            <td className="max-w-[320px] px-5 py-3">
              <div className="truncate font-medium text-fg" title={doc.file_name}>{doc.file_name}</div>
              <div className="truncate text-xs text-muted">
                {doc.company ?? d.noCompany}
                {period && <span className="text-dim"> · {period}</span>}
              </div>
            </td>
            <td className="whitespace-nowrap px-5 py-3">
              <OwnerLabel ownerType={doc.owner_type} username={doc.username} />
            </td>
            <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(doc.page_count)}</td>
            <td className="min-w-[180px] px-5 py-3">
              <StatusBadge status={doc.status} />
              {active && (
                <div className="mt-2">
                  <div className="mb-1 flex justify-between text-[11px] text-dim">
                    <span>{stage}</span>
                    <span className="font-mono">{doc.progress_percent ?? 0}%</span>
                  </div>
                  <div
                    className="h-1 overflow-hidden rounded-full bg-white/10"
                    role="progressbar"
                    aria-valuenow={doc.progress_percent ?? 0}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={stage ?? d.status.processing}
                  >
                    <div className="h-full rounded-full bg-blue-500 transition-[width]" style={{ width: `${doc.progress_percent ?? 0}%` }} />
                  </div>
                </div>
              )}
              {doc.status === "failed" && doc.error_code && (
                <p className="mt-1.5 max-w-[260px] text-xs text-rose-300/90">
                  {processingErrorText(doc.error_code, t)} <span className="font-mono text-dim">({doc.error_code})</span>
                </p>
              )}
              {doc.status === "ready" && (
                <p className="mt-1 text-xs text-dim">
                  {[doc.parsing_engine, doc.chunks != null && fill(d.chunks, { n: doc.chunks })].filter(Boolean).join(" · ")}
                </p>
              )}
            </td>
            <td className="whitespace-nowrap px-5 py-3 text-right font-mono text-fg-2">
              {doc.duration_s != null ? fill(d.seconds, { s: fmt.number(Math.round(doc.duration_s)) }) : "—"}
            </td>
            <td className="whitespace-nowrap px-5 py-3 text-muted">{fmt.dateTime(doc.created_at)}</td>
          </tr>
        );
      })}
    </Table>
  );
};

type Filter = "all" | AdminDocument["status"];

export const DocumentsPage: React.FC = () => {
  const { data, loading } = useAdminData();
  const { t } = useLanguage();
  const d = t.adminPanel.docs;
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const docs = data?.documents ?? [];
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs.filter(
      (doc) =>
        (filter === "all" || doc.status === filter || (filter === "processing" && doc.status === "pending")) &&
        (!q || [doc.file_name, doc.company, doc.ticker, doc.username].some((v) => v?.toLowerCase().includes(q)))
    );
  }, [docs, filter, query]);

  if (!data) return loading ? <Skeleton className="h-96" /> : null;

  const count = (s: Filter) => docs.filter((doc) => doc.status === s || (s === "processing" && doc.status === "pending")).length;
  return (
    <Card>
      <CardHeader
        title={d.title}
        subtitle={fill(d.pageNote, { shown: docs.length, total: data.totals.documents.total })}
        icon={FileText}
      />
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
        <Segmented
          label={d.colStatus}
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: d.all, count: docs.length },
            { value: "processing", label: d.status.processing, count: count("processing") },
            { value: "failed", label: d.status.failed, count: count("failed") },
            { value: "ready", label: d.status.ready, count: count("ready") },
          ]}
        />
        <SearchField value={query} onChange={setQuery} label={d.search} />
      </div>
      <DocumentsTable documents={shown} emptyText={docs.length ? d.noMatch : d.empty} />
    </Card>
  );
};
