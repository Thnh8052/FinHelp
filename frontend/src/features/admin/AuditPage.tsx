import React, { useMemo, useState } from "react";
import { Clock, Coins, Flag, MessagesSquare, Quote } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { MarkdownRenderer } from "../../components/chat/MarkdownRenderer";
import "../../components/chat/chat.css";
import { useAdminData } from "./AdminLayout";
import type { AdminAnswer } from "./types";
import { Card, CardHeader, EmptyState, OwnerLabel, SearchField, Segmented, Skeleton, fill, useFormat } from "./ui";

/** Answers with the question before them; the answer text opens on demand (a native disclosure: keyboard and screen readers for free). */
export const AnswerList: React.FC<{ answers: AdminAnswer[]; emptyTitle: string; emptyHint?: string }> = ({ answers, emptyTitle, emptyHint }) => {
  const { t } = useLanguage();
  const a = t.adminPanel.answers;
  const fmt = useFormat();
  if (!answers.length) return <EmptyState title={emptyTitle} hint={emptyHint} icon={Flag} />;

  return (
    <ul className="divide-y divide-white/5">
      {answers.map((item) => (
        <li key={item.message_id} className="px-5 py-4">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-dim">
            <OwnerLabel ownerType={item.owner_type} username={item.username} />
            <span aria-hidden>·</span>
            <span>{fmt.dateTime(item.created_at)}</span>
            {item.rating === -1 && (
              <span className="inline-flex items-center gap-1 rounded-md bg-negative-soft px-1.5 py-0.5 font-medium text-rose-300">
                <Flag size={11} aria-hidden />
                {item.rated_at ? fill(a.flaggedAt, { time: fmt.dateTime(item.rated_at) }) : a.flaggedTag}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-fg">{item.question || a.noQuestion}</p>
          <details className="group mt-2">
            <summary className="cursor-pointer list-none text-xs font-medium text-blue-400 hover:text-blue-300 [&::-webkit-details-marker]:hidden">
              <span className="group-open:hidden">{a.showAnswer}</span>
              <span className="hidden group-open:inline">{a.hideAnswer}</span>
            </summary>
            <div className="mt-2 max-h-96 overflow-y-auto rounded-lg border border-line bg-field px-3 py-2.5 text-[13px]">
              <MarkdownRenderer content={item.answer} />
            </div>
          </details>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-muted">
            <span className="inline-flex items-center gap-1">
              <Coins size={12} aria-hidden />
              {fill(a.tokens, { n: fmt.number(item.tokens) })}
            </span>
            {item.latency_ms != null && (
              <span className="inline-flex items-center gap-1">
                <Clock size={12} aria-hidden />
                {fill(a.latency, { s: fmt.seconds(item.latency_ms) })}
              </span>
            )}
            <span className="inline-flex items-center gap-1">
              <Quote size={12} aria-hidden />
              {fill(a.citations, { n: item.citations })}
            </span>
            {item.model && <span className="text-dim">{item.model}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
};

type Filter = "all" | "flagged";

export const AuditPage: React.FC = () => {
  const { data, loading } = useAdminData();
  const { t } = useLanguage();
  const a = t.adminPanel.answers;
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const source = filter === "flagged" ? data?.flagged ?? [] : data?.recent_answers ?? [];
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? source.filter((x) => [x.question, x.answer, x.username].some((v) => v?.toLowerCase().includes(q))) : source;
  }, [source, query]);

  if (!data) return loading ? <Skeleton className="h-96" /> : null;

  return (
    <Card>
      <CardHeader title={a.auditTitle} subtitle={fill(a.auditNote, { n: data.window_days })} icon={MessagesSquare} />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <Segmented
          label={a.auditTitle}
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: a.filterAll, count: data.recent_answers.length },
            { value: "flagged", label: a.filterFlagged, count: data.totals.flagged_total },
          ]}
        />
        <SearchField value={query} onChange={setQuery} label={a.search} />
      </div>
      <AnswerList
        answers={shown}
        emptyTitle={query ? a.noMatch : filter === "flagged" ? a.flaggedEmpty : a.empty}
        emptyHint={!query && filter === "flagged" ? a.flaggedHint : undefined}
      />
    </Card>
  );
};
