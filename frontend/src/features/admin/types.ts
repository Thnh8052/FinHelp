/** GET /auth/admin/overview (backend/app/modules/admin/overview.py). Dates come without a zone: they are UTC. */

export type OwnerType = "user" | "guest" | "system" | "unknown";

interface Owner {
  owner_type: OwnerType;
  username: string | null;
  notebook_title: string | null;
}

export interface WindowTotals {
  questions: number;
  tokens: number;
  avg_latency_ms: number | null;
}

export interface DayUsage {
  date: string; // YYYY-MM-DD
  questions: number;
  prompt_tokens: number;
  completion_tokens: number;
  flagged: number;
}

export interface AdminDocument extends Owner {
  document_id: string;
  file_name: string;
  company: string | null;
  ticker: string | null;
  fiscal_year: number | null;
  report_type: string | null;
  page_count: number;
  file_size_bytes: number;
  status: "pending" | "processing" | "ready" | "failed";
  error_code: string | null;
  parsing_engine: string | null;
  stage: string | null;
  progress_percent: number | null;
  chunks: number | null;
  duration_s: number | null;
  created_at: string;
}

export interface AdminAnswer extends Owner {
  message_id: string;
  notebook_id: string;
  question: string;
  answer: string;
  tokens: number;
  latency_ms: number | null;
  model: string | null;
  rating: number | null;
  rated_at: string | null; // when the user reported it
  citations: number;
  created_at: string;
}

export interface AdminUser {
  user_id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: "user" | "admin";
  is_active: boolean;
  total_tokens: number;
  notebooks: number;
  created_at: string | null;
  last_login_at: string | null;
}

export interface AdminOverview {
  window_days: number;
  generated_at: string;
  totals: {
    current: WindowTotals;
    previous: WindowTotals;
    flagged_total: number;
    users_total: number;
    users_active: number;
    documents: { total: number; ready: number; processing: number; failed: number };
  };
  series: DayUsage[];
  by_model: { model: string; questions: number; tokens: number }[];
  documents: AdminDocument[];
  flagged: AdminAnswer[];
  recent_answers: AdminAnswer[];
  users: AdminUser[];
  services: Record<string, number | null>; // latency in ms, null when the service did not answer
}
