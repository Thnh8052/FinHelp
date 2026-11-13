import React, { useMemo, useState } from "react";
import { CheckCircle2, MinusCircle, ShieldCheck, Users } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useAdminData } from "./AdminLayout";
import { Card, CardHeader, EmptyState, SearchField, Skeleton, Table, fill, useFormat } from "./ui";

export const UsersPage: React.FC = () => {
  const { data, loading } = useAdminData();
  const { t } = useLanguage();
  const u = t.adminPanel.users;
  const fmt = useFormat();
  const [query, setQuery] = useState("");

  const users = data?.users ?? [];
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? users.filter((x) => [x.username, x.email, x.full_name].some((v) => v?.toLowerCase().includes(q))) : users;
  }, [users, query]);

  if (!data) return loading ? <Skeleton className="h-96" /> : null;

  return (
    <Card>
      <CardHeader
        title={u.title}
        subtitle={fill(u.summary, { active: data.totals.users_active, total: data.totals.users_total })}
        icon={Users}
        action={<SearchField value={query} onChange={setQuery} label={u.search} />}
      />
      {shown.length ? (
        <Table caption={u.title} head={[u.colUser, u.colRole, u.colStatus, u.colNotebooks, u.colTokens, u.colCreated, u.colLastLogin]} alignRight={[3, 4]}>
          {shown.map((x) => (
            <tr key={x.user_id} className="transition-colors hover:bg-white/[0.02]">
              <td className="min-w-[220px] px-5 py-3">
                <div className="font-medium text-fg">{x.full_name || `@${x.username}`}</div>
                <div className="text-xs text-muted">
                  {x.full_name && <span className="text-dim">@{x.username} · </span>}
                  {x.email}
                </div>
              </td>
              <td className="whitespace-nowrap px-5 py-3">
                {x.role === "admin" ? (
                  <span className="inline-flex items-center gap-1 rounded-md bg-accent/15 px-2 py-0.5 text-xs font-medium text-blue-300">
                    <ShieldCheck size={12} aria-hidden />
                    {u.roleAdmin}
                  </span>
                ) : (
                  <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs font-medium text-fg-2">{u.roleUser}</span>
                )}
              </td>
              <td className="whitespace-nowrap px-5 py-3">
                <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${x.is_active ? "text-positive" : "text-muted"}`}>
                  {x.is_active ? <CheckCircle2 size={13} aria-hidden /> : <MinusCircle size={13} aria-hidden />}
                  {x.is_active ? u.active : u.inactive}
                </span>
              </td>
              <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(x.notebooks)}</td>
              <td className="px-5 py-3 text-right font-mono text-fg-2">{fmt.number(x.total_tokens)}</td>
              <td className="whitespace-nowrap px-5 py-3 text-muted">{fmt.date(x.created_at)}</td>
              <td className="whitespace-nowrap px-5 py-3 text-muted">{x.last_login_at ? fmt.dateTime(x.last_login_at) : u.never}</td>
            </tr>
          ))}
        </Table>
      ) : (
        <EmptyState title={users.length ? u.noMatch : u.empty} icon={Users} />
      )}
    </Card>
  );
};
