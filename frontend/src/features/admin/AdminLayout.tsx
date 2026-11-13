import React, { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext } from "react-router-dom";
import { ArrowLeft, Coins, FileText, LayoutDashboard, LogOut, Menu, MessagesSquare, RefreshCw, ShieldCheck, Users, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { apiRequest, errorText } from "../../services/api";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import type { AdminOverview } from "./types";
import { Segmented, fill, useFormat } from "./ui";

const WINDOWS = ["7", "14", "30", "90"] as const;
type WindowDays = (typeof WINDOWS)[number];

export interface AdminContext {
  data: AdminOverview | null;
  loading: boolean;
}

export const useAdminData = () => useOutletContext<AdminContext>();

type NavKey = "overview" | "documents" | "audit" | "tokens" | "users";
const NAV: { key: NavKey; to: string; icon: LucideIcon }[] = [
  { key: "overview", to: "/admin", icon: LayoutDashboard },
  { key: "documents", to: "/admin/documents", icon: FileText },
  { key: "audit", to: "/admin/audit", icon: MessagesSquare },
  { key: "tokens", to: "/admin/tokens", icon: Coins },
  { key: "users", to: "/admin/users", icon: Users },
];

export const AdminLayout: React.FC = () => {
  const { t } = useLanguage();
  const p = t.adminPanel;
  const fmt = useFormat();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [days, setDays] = useState<WindowDays>("14");
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await apiRequest<AdminOverview>(`/auth/admin/overview?days=${days}`));
    } catch (err) {
      setError(errorText(err, t, p.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [days, t, p.loadFailed]);

  useEffect(() => {
    load();
  }, [days]); // eslint-disable-line react-hooks/exhaustive-deps -- reload on a new window, not on a language change

  useEffect(() => setMenuOpen(false), [location.pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const current = NAV.find((n) => (n.to === "/admin" ? location.pathname === "/admin" : location.pathname.startsWith(n.to))) ?? NAV[0];
  const badges: Partial<Record<NavKey, number>> = {
    documents: data ? data.totals.documents.processing + data.totals.documents.failed : 0,
    audit: data?.totals.flagged_total ?? 0,
  };

  /** In the phone drawer the close button takes the place of the Admin tag. */
  const sidebar = (inDrawer: boolean) => (
    <nav aria-label={p.nav.label} className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between gap-2 border-b border-line px-4">
        <FinHelpLogo size="sm" onClick={() => navigate("/")} />
        {inDrawer ? (
          <button
            type="button"
            autoFocus
            onClick={() => setMenuOpen(false)}
            aria-label={p.nav.closeMenu}
            className="flex size-9 items-center justify-center rounded-md text-muted hover:bg-white/5 hover:text-fg"
          >
            <X size={18} aria-hidden />
          </button>
        ) : (
        <span className="inline-flex items-center gap-1 rounded-md border border-blue-500/30 bg-accent/15 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-blue-300">
          <ShieldCheck size={12} aria-hidden />
          Admin
        </span>
        )}
      </div>
      <ul className="flex flex-1 flex-col gap-1 p-3">
        {NAV.map(({ key, to, icon: Icon }) => (
          <li key={key}>
            <NavLink
              to={to}
              end={to === "/admin"}
              className={({ isActive }) =>
                `group flex h-10 items-center gap-3 rounded-lg px-3 text-[13.5px] font-medium transition-colors ${
                  isActive ? "bg-accent/15 text-fg ring-1 ring-blue-500/30" : "text-muted hover:bg-white/5 hover:text-fg"
                }`
              }
            >
              <Icon size={17} aria-hidden className="shrink-0" />
              <span className="flex-1 truncate">{p.nav[key]}</span>
              {!!badges[key] && (
                <span
                  className="rounded-full bg-amber-400/15 px-1.5 font-mono text-[11px] font-semibold text-amber-300"
                  aria-label={fill(p.nav.needsAttention, { n: badges[key]! })}
                >
                  {badges[key]}
                </span>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="flex flex-col gap-1 border-t border-line p-3">
        <button
          type="button"
          onClick={() => navigate("/app")}
          className="flex h-10 items-center gap-3 rounded-lg px-3 text-[13.5px] font-medium text-muted transition-colors hover:bg-white/5 hover:text-fg"
        >
          <ArrowLeft size={17} aria-hidden />
          {p.nav.backToChat}
        </button>
        <div className="mt-1 flex items-center gap-3 rounded-lg bg-white/[0.03] px-3 py-2.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold uppercase text-white">
            {(user?.username ?? "A").slice(0, 1)}
          </span>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[13px] font-semibold text-fg">{user?.full_name || user?.username}</div>
            <div className="truncate text-xs text-dim">{user?.email}</div>
          </div>
          <button
            type="button"
            onClick={async () => {
              await logout();
              navigate("/");
            }}
            aria-label={t.common.signOut}
            title={t.common.signOut}
            className="flex size-8 items-center justify-center rounded-md text-muted hover:bg-white/5 hover:text-rose-300"
          >
            <LogOut size={15} aria-hidden />
          </button>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="flex h-full bg-app text-fg">
      <aside className="hidden w-64 shrink-0 border-r border-line bg-panel lg:block">{sidebar(false)}</aside>

      {menuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label={p.nav.label}>
          <button type="button" aria-label={p.nav.closeMenu} className="absolute inset-0 bg-black/60" onClick={() => setMenuOpen(false)} />
          <aside className="relative h-full w-72 max-w-[85vw] border-r border-line bg-panel">{sidebar(true)}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-16 flex-wrap items-center gap-3 border-b border-line bg-panel/60 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={() => setMenuOpen(true)}
            aria-label={p.nav.openMenu}
            className="flex size-9 items-center justify-center rounded-lg border border-line text-muted hover:text-fg lg:hidden"
          >
            <Menu size={18} aria-hidden />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold tracking-tight text-fg">{p.nav[current.key]}</h1>
            <p className="truncate text-[13px] text-muted">{p.subtitles[current.key]}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Segmented
              label={p.window}
              value={days}
              onChange={setDays}
              options={WINDOWS.map((d) => ({ value: d, label: fill(p.lastDays, { n: d }) }))}
            />
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-line-strong px-3 text-[13px] font-medium text-fg-2 transition-colors hover:bg-white/5 hover:text-fg"
            >
              <RefreshCw size={14} aria-hidden className={loading ? "animate-spin" : ""} />
              <span className="hidden sm:inline">{p.refresh}</span>
            </button>
            <LanguageToggle size="sm" />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-6" aria-busy={loading}>
          <div className="mx-auto flex max-w-[1400px] flex-col gap-6">
            {error && (
              <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-negative-soft px-4 py-3 text-sm text-rose-200">
                {error}
                <button type="button" onClick={load} className="rounded-md border border-rose-400/40 px-3 py-1 text-xs font-medium hover:bg-rose-500/10">
                  {t.common.retry}
                </button>
              </div>
            )}
            <Outlet context={{ data, loading } satisfies AdminContext} />
            {data && (
              <p className="text-right text-xs text-dim">{fill(p.updatedAt, { time: fmt.dateTime(data.generated_at) })}</p>
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
