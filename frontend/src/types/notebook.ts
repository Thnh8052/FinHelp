export interface Notebook {
  notebook_id: string;
  user_id: string;
  title: string;
  description?: string;
  tags: string[];
  document_ids: string[];
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
  file_path: string;
  page_count: number;
  parsing_status: "pending" | "processing" | "completed" | "failed";
  indexing_status: "pending" | "indexing" | "completed" | "failed";
  error_message?: string;
  parsing_engine?: string;
  created_at: string;
}

/** Giống catalog_edit.needs_confirmation ở backend: chưa xác minh tên / kỳ, hoặc thiếu tên / năm, và chủ chưa xác nhận. */
export const needsCatalogConfirmation = (d: DocumentRecord): boolean => {
  const m = d.metadata || {};
  return (
    d.indexing_status === "completed" &&
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
  !!d && d.indexing_status !== "completed" && d.parsing_status !== "failed";

export const isDocFailed = (d: DocumentRecord | null | undefined): boolean => d?.parsing_status === "failed";

export interface IngestionJob {
  job_id: string;
  document_id: string;
  notebook_id: string;
  status: "pending" | "parsing" | "chunking" | "indexing_qdrant" | "completed" | "failed";
  progress_percent: number;
  error_log?: string;
}
