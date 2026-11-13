import React from "react";
import { AlertTriangle, CheckCircle2, Clock, Inbox, Loader2, Search, TrendingDown, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import type { AdminDocument, OwnerType } from "./types";

/* ---------- formatting ---------- */

const localeOf = (lang: string) => (lang === "vi" ? "vi-VN" : "en-US");

/** The backend writes UTC dates without a zone: read them as UTC. */
export const parseUtc = (value: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);

export function useFormat() {
  const { lang } = useLanguage();
  const locale = localeOf(lang);
  return {
    number: (n: number) => n.toLocaleString(locale),
    compact: (n: number) => new Intl.NumberFormat(locale, { notation: "compact", maximumFractionDigits: 1 }).format(n),
    seconds: (ms: number) => (ms / 1000).toLocaleString(locale, { maximumFractionDigits: 1 }),
    dateTime: (value: string | null) =>
      value ? parseUtc(value).toLocaleString(locale, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—",
    date: (value: string | null) => (value ? parseUtc(value).toLocaleDateString(locale, { day: "2-digit", month: "2-digit", year: "numeric" }) : "—"),
    /** "2026-11-12" -> "12/11" (chart axis) */
    day: (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString(locale, { day: "2-digit", month: "2-digit", timeZone: "UTC" }),
  };
}

export const fill = (text: string, params: Record<string, string | number>) =>
  text.replace(/\{(\w+)\}/g, (_, key: string) => String(params[key] ?? ""));

/* ---------- layout pieces ---------- */

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({ className = "", children }) => (
  <section className={`rounded-xl border border-line bg-card ${className}`}>{children}</section>
);

export const CardHeader: React.FC<{ title: string; subtitle?: string; icon?: LucideIcon; action?: React.ReactNode }> = ({
  title,
  subtitle,
  icon: Icon,
  action,
}) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
    <div className="flex min-w-0 items-start gap-3">
      {Icon && (
        <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent/15 text-blue-400">
          <Icon size={16} aria-hidden />
        </span>
      )}
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold leading-snug text-fg">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
      </div>
    </div>
    {action}
  </div>
);

interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  sub: string;
  /** relative change vs the previous window; null hides the trend chip */
  change?: number | null;
  tone?: "default" | "warning";
}

export const KpiCard: React.FC<KpiCardProps> = ({ label, value, icon: Icon, sub, change = null, tone = "default" }) => {
  const up = (change ?? 0) >= 0;
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-muted">{label}</span>
        <span
          className={`flex size-8 items-center justify-center rounded-lg ${
            tone === "warning" ? "bg-amber-400/12 text-amber-300" : "bg-accent/15 text-blue-400"
          }`}
        >
          <Icon size={16} aria-hidden />
        </span>
      </div>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="font-mono text-[26px] font-semibold leading-none tracking-tight text-fg">{value}</span>
        {change !== null && (
          <span
            className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-xs font-medium ${
              up ? "bg-positive-soft text-positive" : "bg-negative-soft text-negative"
            }`}
          >
            {up ? <TrendingUp size={12} aria-hidden /> : <TrendingDown size={12} aria-hidden />}
            {up ? "+" : ""}
            {Math.round(change * 100)}%
          </span>
        )}
      </div>
      <p className="text-[13px] text-dim">{sub}</p>
    </Card>
  );
};

/* ---------- status ---------- */

const STATUS_STYLE: Record<AdminDocument["status"], { icon: LucideIcon; className: string; spin?: boolean }> = {
  ready: { icon: CheckCircle2, className: "bg-positive-soft text-positive" },
  processing: { icon: Loader2, className: "bg-accent/15 text-blue-300", spin: true },
  pending: { icon: Clock, className: "bg-amber-400/12 text-amber-300" },
  failed: { icon: AlertTriangle, className: "bg-negative-soft text-rose-300" },
};

export const StatusBadge: React.FC<{ status: AdminDocument["status"] }> = ({ status }) => {
  const { t } = useLanguage();
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.pending;
  const Icon = style.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${style.className}`}>
      <Icon size={12} aria-hidden className={style.spin ? "animate-spin" : ""} />
      {t.adminPanel.docs.status[status] ?? status}
    </span>
  );
};

/** Who owns a notebook: the account name, or what kind of owner it is when there is no account. */
export const OwnerLabel: React.FC<{ ownerType: OwnerType; username: string | null }> = ({ ownerType, username }) => {
  const { t } = useLanguage();
  if (ownerType === "user" && username) return <span className="text-fg-2">@{username}</span>;
  const text = ownerType === "guest" ? t.adminPanel.guest : ownerType === "system" ? t.adminPanel.system : "—";
  return <span className="text-dim">{text}</span>;
};

/* ---------- states and controls ---------- */

export const EmptyState: React.FC<{ title: string; hint?: string; icon?: LucideIcon }> = ({ title, hint, icon: Icon = Inbox }) => (
  <div role="status" className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
    <Icon size={28} className="text-dim" aria-hidden />
    <p className="text-sm font-medium text-fg-2">{title}</p>
    {hint && <p className="max-w-sm text-[13px] text-dim">{hint}</p>}
  </div>
);

export const Skeleton: React.FC<{ className?: string }> = ({ className = "" }) => (
  <div className={`animate-pulse rounded-lg bg-white/5 ${className}`} />
);

export const SearchField: React.FC<{ value: string; onChange: (v: string) => void; label: string }> = ({ value, onChange, label }) => (
  <label className="relative block w-full sm:w-72">
    <span className="sr-only">{label}</span>
    <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-dim" aria-hidden />
    <input
      type="search"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={label}
      className="h-9 w-full rounded-lg border border-line-strong bg-field pl-9 pr-3 text-[13px] text-fg placeholder:text-dim focus:border-blue-500"
    />
  </label>
);

interface SegmentedProps<T extends string> {
  label: string;
  value: T;
  options: { value: T; label: string; count?: number }[];
  onChange: (v: T) => void;
}

export function Segmented<T extends string>({ label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-lg border border-line bg-field p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={`inline-flex h-7 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition-colors ${
            value === o.value ? "bg-card-hover text-fg shadow-sm ring-1 ring-line-strong" : "text-muted hover:text-fg"
          }`}
        >
          {o.label}
          {o.count !== undefined && <span className="font-mono text-[11px] text-dim">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

/** Table shell: scrolls sideways inside its card on narrow screens instead of widening the page. */
export const Table: React.FC<{ caption: string; head: string[]; children: React.ReactNode; alignRight?: number[] }> = ({
  caption,
  head,
  children,
  alignRight = [],
}) => (
  <div className="overflow-x-auto">
    <table className="w-full min-w-[720px] border-collapse text-left text-[13px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-line text-xs uppercase tracking-wide text-dim">
          {head.map((h, i) => (
            <th key={h} scope="col" className={`whitespace-nowrap px-5 py-2.5 font-medium ${alignRight.includes(i) ? "text-right" : ""}`}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-white/5">{children}</tbody>
    </table>
  </div>
);
