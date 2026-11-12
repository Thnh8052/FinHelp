/** Một notebook là một đoạn chat. */
export interface Notebook {
  notebook_id: string;
  title: string;
  message_count: number;
  /** Chỉ có ở danh sách sổ tay. */
  document_count?: number;
  processing_count?: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentMetadata {
  company_name?: string | null;
  ticker?: string | null;
  report_type?: string | null;
  fiscal_year?: number | null;
  fiscal_quarter?: number | null;
  catalog_unverified?: string[];
  catalog_confirmed?: boolean;
  user_override_unverified?: string[];
}

export interface DocumentRecord {
  metadata?: DocumentMetadata;
  document_id: string;
  notebook_id: string;
  file_name: string;
  file_size_bytes: number;
  page_count: number;
  status: "pending" | "processing" | "ready" | "failed";
  error_message?: string;
  /** Tài liệu được đọc bằng cách dự phòng: một số bảng có thể chưa chính xác. */
  tables_may_be_inaccurate?: boolean;
  created_at: string;
}

/** Giống catalog_edit.needs_confirmation ở backend: chưa xác minh tên / kỳ, hoặc thiếu tên / năm, và chủ chưa xác nhận. */
export const needsCatalogConfirmation = (d: DocumentRecord): boolean => {
  const m = d.metadata || {};
  return (
    d.status === "ready" &&
    !m.catalog_confirmed &&
    ((m.catalog_unverified || []).length > 0 || !m.company_name || !m.fiscal_year)
  );
};

/** "AMD | 10-K | FY2025" từ catalog (như document_label ở backend), tên file khi chưa có catalog. */
export const documentLabel = (d: DocumentRecord): string => {
  const m = d.metadata || {};
  const period = m.fiscal_year ? `FY${m.fiscal_year}${m.fiscal_quarter ? ` Q${m.fiscal_quarter}` : ""}` : "";
  return [m.company_name, m.report_type, period].filter(Boolean).join(" | ") || d.file_name;
};

/** Tài liệu vừa tải lên và chưa xử lý xong (chưa hỏi đáp được). */
export const isDocProcessing = (d: DocumentRecord | null | undefined): boolean =>
  !!d && (d.status === "pending" || d.status === "processing");

export const isDocFailed = (d: DocumentRecord | null | undefined): boolean => d?.status === "failed";

/** A legal name the document itself prints, with the pages it is on: the catalog form offers these first. */
export interface NameCandidate {
  name: string;
  pages: number[];
}

/** GET /documents/{id}/catalog */
export interface CatalogPayload {
  document_id: string;
  file_name: string;
  needs_confirmation: boolean;
  report_types: string[];
  metadata: {
    company_name?: string | null;
    ticker?: string | null;
    aliases?: string[];
    report_type?: string | null;
    fiscal_year?: number | null;
    fiscal_quarter?: number | null;
    period_end?: string | null;
    catalog_unverified?: string[];
    name_candidates?: NameCandidate[];
  };
}

/** PATCH /documents/{id}/catalog */
export interface CatalogUpdate {
  company_name: string;
  ticker: string | null;
  aliases: string[];
  report_type: string;
  fiscal_year: number;
  fiscal_quarter: number | null;
  period_end: string | null;
}

export interface IngestionJob {
  job_id: string;
  document_id: string;
  notebook_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress_percent: number;
}
