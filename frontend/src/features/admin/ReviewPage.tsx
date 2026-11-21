import React, { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ListChecks, Wrench, RotateCcw } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { apiRequest, errorText } from "../../services/api";
import { MarkdownRenderer } from "../../components/chat/MarkdownRenderer";
import "../../components/chat/chat.css";
import { useAdminData } from "./AdminLayout";
import { AnswerStepsPanel } from "./AnswerStepsPanel";
import { labelTone, reviewPath } from "./reviewQuery";
import type { ReviewItem, ReviewLabel, ReviewQueue, ReviewStatus } from "./types";
import { REVIEW_LABELS } from "./types";
import { Card, CardHeader, EmptyState, OwnerLabel, Segmented, Skeleton, fill, useFormat } from "./ui";

const TONE = { negative: "bg-negative-soft text-negative-text", warn: "bg-warn/15 text-warn-text", neutral: "bg-hover text-fg-2" } as const;
type Verdict = "ok" | "needs_fix" | "open";

/** Answers with a problem, found from what the chat stores with each answer (backend admin/review.py); the admin marks each one once checked. */
export const ReviewPage: React.FC = () => {
  const { days, user, reload } = useAdminData();
  const { t } = useLanguage();
  const r = t.adminPanel.review;
  const [status, setStatus] = useState<ReviewStatus>("open");
  const [label, setLabel] = useState<ReviewLabel | "">("");
  const [queue, setQueue] = useState<ReviewQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setQueue(await apiRequest<ReviewQueue>(reviewPath({ days, user, label, status })));
    } catch (err) {
      setError(errorText(err, t, t.adminPanel.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [days, user, label, status, t]);

  useEffect(() => {
    load();
  }, [days, user, label, status]); // eslint-disable-line react-hooks/exhaustive-deps -- not on a language change

  const decide = async (messageId: string, verdict: Verdict, note: string) => {
    await apiRequest(`/auth/admin/review/${encodeURIComponent(messageId)}`, { method: "POST", body: JSON.stringify({ status: verdict, note }) });
    await load();
    reload(); // the menu badge counts the open answers
  };

  const chip = (value: ReviewLabel | "", text: string, count?: number) => (
    <button
      key={value || "all"}
      type="button"
      aria-pressed={label === value}
      onClick={() => setLabel(value)}
      title={value ? r.hints[value] : undefined}
      className={`inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12.5px] font-medium transition-colors ${
        label === value ? "border-accent/40 bg-accent/15 text-fg" : "border-line text-muted hover:bg-hover hover:text-fg"
      }`}
    >
      {text}
      {count != null && <span className="font-mono text-[11px] text-dim">{count}</span>}
    </button>
  );

  return (
    <Card>
      <CardHeader title={r.title} subtitle={fill(r.note, { n: days })} icon={ListChecks} />
      <div className="flex flex-col gap-3 border-b border-line px-5 py-3">
        <Segmented
          label={r.statusLabel}
          value={status}
          onChange={setStatus}
          options={[
            { value: "open", label: r.statusOpen, count: queue?.open_total },
            { value: "reviewed", label: r.statusReviewed },
            { value: "all", label: r.statusAll },
          ]}
        />
        <div role="group" aria-label={r.problemsLabel} className="flex flex-wrap gap-2">
          {chip("", r.allProblems)}
          {REVIEW_LABELS.map((l) => chip(l, r.labels[l], queue?.counts[l]))}
        </div>
      </div>
      {error && (
        <div role="alert" className="mx-5 mt-4 rounded-lg border border-negative/30 bg-negative-soft px-3 py-2 text-sm text-negative-text">
          {error}
        </div>
      )}
      {loading && !queue ? (
        <Skeleton className="m-5 h-64" />
      ) : queue?.items.length ? (
        <ul className="divide-y divide-line" aria-busy={loading}>
          {queue.items.map((item) => (
            <ReviewEntry key={`${item.message_id}-${item.review?.status ?? "open"}`} item={item} onDecide={decide} />
          ))}
        </ul>
      ) : (
        <EmptyState title={status === "reviewed" ? r.emptyReviewed : r.empty} hint={status === "reviewed" ? undefined : r.emptyHint} icon={ListChecks} />
      )}
    </Card>
  );
};

const ReviewEntry: React.FC<{ item: ReviewItem; onDecide: (id: string, verdict: Verdict, note: string) => Promise<void> }> = ({ item, onDecide }) => {
  const { t } = useLanguage();
  const r = t.adminPanel.review;
  const a = t.adminPanel.answers;
  const fmt = useFormat();
  const [note, setNote] = useState(item.review?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const noteId = `review-note-${item.message_id}`;

  const act = async (verdict: Verdict) => {
    setBusy(true);
    setError(null);
    try {
      await onDecide(item.message_id, verdict, note);
    } catch (err) {
      setError(errorText(err, t, r.saveFailed));
      setBusy(false);
    }
  };
  const button = "inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-[13px] font-medium transition-colors disabled:opacity-60";

  return (
    <li className="px-5 py-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-dim">
        <OwnerLabel ownerType={item.owner_type} username={item.username} />
        <span aria-hidden>·</span>
        <span>{fmt.dateTime(item.created_at)}</span>
        {item.labels.map((l) => (
          <span key={l} title={r.hints[l]} className={`rounded-md px-1.5 py-0.5 font-medium ${TONE[labelTone(l)]}`}>
            {r.labels[l]}
          </span>
        ))}
        {item.review && (
          <span className={`rounded-md px-1.5 py-0.5 font-medium ${item.review.status === "ok" ? "bg-positive-soft text-positive-text" : "bg-negative-soft text-negative-text"}`}>
            {item.review.status === "ok" ? r.reviewedOk : r.reviewedNeedsFix} · {fill(r.reviewedBy, { by: item.review.by, time: fmt.dateTime(item.review.at) })}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-fg">{item.question || a.noQuestion}</p>
      <details className="group mt-2">
        <summary className="cursor-pointer list-none text-xs font-medium text-accent-text hover:underline [&::-webkit-details-marker]:hidden">
          <span className="group-open:hidden">{a.showAnswer}</span>
          <span className="hidden group-open:inline">{a.hideAnswer}</span>
        </summary>
        <div className="mt-2 max-h-96 overflow-y-auto rounded-lg border border-line bg-field px-3 py-2.5 text-[13px]">
          <MarkdownRenderer content={item.answer} />
        </div>
      </details>
      <details className="mt-2">
        <summary className="cursor-pointer text-xs font-medium text-muted hover:text-fg">{r.why}</summary>
        <dl className="mt-2 grid gap-2 rounded-lg border border-line px-3 py-2.5 text-[12.5px] text-fg-2">
          {item.labels.map((l) => (
            <dd key={l}>{r.hints[l]}</dd>
          ))}
          {item.unverified.length > 0 && <Fact term={r.unverified} items={item.unverified} />}
          {item.degraded.length > 0 && <Fact term={r.degraded} items={item.degraded} />}
          {item.intent && item.intent !== "retrieval_rag" && <Fact term={r.handledAs} items={[item.intent]} />}
          {item.notes.length > 0 && <Fact term={r.notes} items={item.notes} />}
        </dl>
      </details>
      <AnswerStepsPanel messageId={item.message_id} />
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label htmlFor={noteId} className="sr-only">
          {r.noteLabel}
        </label>
        <input
          id={noteId}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={2000}
          placeholder={r.notePlaceholder}
          className="h-9 min-w-56 flex-1 rounded-lg border border-line bg-field px-3 text-[13px] text-fg placeholder:text-dim focus:border-accent focus:outline-none"
        />
        {item.review ? (
          <button type="button" disabled={busy} onClick={() => act("open")} className={`${button} border-line-strong text-fg-2 hover:bg-hover hover:text-fg`}>
            <RotateCcw size={14} aria-hidden />
            {r.reopen}
          </button>
        ) : (
          <>
            <button type="button" disabled={busy} onClick={() => act("ok")} className={`${button} border-positive/40 text-positive-text hover:bg-positive-soft`}>
              <CheckCircle2 size={14} aria-hidden />
              {r.markOk}
            </button>
            <button type="button" disabled={busy} onClick={() => act("needs_fix")} className={`${button} border-negative/40 text-negative-text hover:bg-negative-soft`}>
              <Wrench size={14} aria-hidden />
              {r.markNeedsFix}
            </button>
          </>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-2 text-xs text-negative-text">
          {error}
        </p>
      )}
    </li>
  );
};

const Fact: React.FC<{ term: string; items: string[] }> = ({ term, items }) => (
  <div>
    <dt className="font-medium text-fg">{term}</dt>
    {items.map((x, i) => (
      <dd key={i} className="mt-0.5 break-words text-muted">
        {x}
      </dd>
    ))}
  </div>
);
