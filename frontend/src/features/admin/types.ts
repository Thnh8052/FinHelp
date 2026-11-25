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
  /** Pages the user is told to check: tables that may be misread, scanned pages with no text (ingestion/parse_check.py). */
  parse_issues?: { tables?: number[]; unread?: number[]; figures?: number[] };
  /** How reading went: pages read again, how many replaced, refused (by reason), pictures described (ingestion/page_quality.py, figures.py). */
  read_report?: { ocr_bad_pages?: number; ocr_replaced_pages?: number; ocr_rejected?: Record<string, number> };
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
  user: string | null; // the user filter: a user id, "guests", or null for everyone
  review_open: number; // answers waiting in the review queue
}

/** GET /auth/admin/review (backend/app/modules/admin/review.py): answers with a problem, found from what the chat stores with each answer. */
export const REVIEW_LABELS = ["user_report", "not_traced", "blocked", "not_found", "partial", "degraded", "refused", "safety", "slow", "guard_sample"] as const;
export type ReviewLabel = (typeof REVIEW_LABELS)[number];
export type ReviewStatus = "open" | "reviewed" | "all";

export interface ReviewState {
  status: "ok" | "needs_fix";
  note: string;
  by: string;
  at: string;
}

export interface ReviewItem extends AdminAnswer {
  labels: ReviewLabel[];
  review: ReviewState | null;
  intent: string | null; // how the chat handled it (retrieval_rag, period_unavailable, refuse_advice...)
  status: string | null; // answered | partial | not_found | clarify
  unverified: string[]; // figures the answer check could not trace
  notes: string[]; // what the answer prompt was told for this question
  degraded: string[]; // steps dropped because they were too slow
  flagged_pages: FlaggedPage[]; // cited pages that were read with a problem at upload (backend admin/review.flagged_pages)
}

export type PageFlag = "may_be_misread" | "read_from_image" | "from_figure" | "picture_unread";
export interface FlaggedPage {
  document_id: string;
  page: number;
  flags: PageFlag[];
  file_name: string | null; // null once the document was deleted
}

export interface ReviewQueue {
  items: ReviewItem[];
  counts: Record<ReviewLabel, number>;
  open_total: number;
  window_days: number;
}
