import React, { useEffect, useState } from "react";
import { authService } from "../../services/auth";
import { CloseIcon } from "../common/Icons";
import "../auth/auth.css";

interface NameCandidate {
  name: string;
  pages: number[];
}

interface CatalogPayload {
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

interface CatalogFormProps {
  documentId: string | null;
  onClose: () => void;
  onSaved: (documentId: string) => void;
}

const OTHER = "__other__";

const authHeaders = (): Record<string, string> => {
  const token = authService.getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Mẫu xác nhận danh tính tài liệu: tên công ty chọn từ các tên tìm được trong tài liệu (kèm trang), chỉ gõ tay khi không có
 * tên đúng; mã CK, tên khác, loại báo cáo, năm / quý, ngày kết thúc kỳ. Backend kiểm lại mọi trường (422 khi sai dạng).
 */
export const CatalogForm: React.FC<CatalogFormProps> = ({ documentId, onClose, onSaved }) => {
  const [data, setData] = useState<CatalogPayload | null>(null);
  const [choice, setChoice] = useState<string>(OTHER);
  const [typedName, setTypedName] = useState("");
  const [ticker, setTicker] = useState("");
  const [aliases, setAliases] = useState("");
  const [reportType, setReportType] = useState("");
  const [fiscalYear, setFiscalYear] = useState("");
  const [quarter, setQuarter] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!documentId) return;
    setError(null);
    setData(null);
    fetch(`/api/v1/documents/${documentId}/catalog`, { headers: authHeaders() })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
        return res.json();
      })
      .then((d: CatalogPayload) => {
        const m = d.metadata;
        const candidates = m.name_candidates || [];
        const known = candidates.find((c) => c.name === m.company_name);
        setData(d);
        setChoice(known ? known.name : candidates.length && !m.company_name ? candidates[0].name : OTHER);
        setTypedName(known ? "" : m.company_name || "");
        setTicker(m.ticker || "");
        setAliases((m.aliases || []).join(", "));
        setReportType(m.report_type || d.report_types[0] || "");
        setFiscalYear(m.fiscal_year ? String(m.fiscal_year) : "");
        setQuarter(m.fiscal_quarter ? String(m.fiscal_quarter) : "");
        setPeriodEnd(m.period_end || "");
      })
      .catch((e: Error) => setError(`Không tải được thông tin tài liệu: ${e.message}`));
  }, [documentId]);

  if (!documentId) return null;

  const unverified = new Set(data?.metadata.catalog_unverified || []);
  const flag = (field: string) => (unverified.has(field) ? { borderColor: "#f59e0b" } : undefined);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const res = await fetch(`/api/v1/documents/${documentId}/catalog`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          company_name: choice === OTHER ? typedName : choice,
          ticker: ticker || null,
          aliases: aliases
            .split(",")
            .map((a) => a.trim())
            .filter(Boolean),
          report_type: reportType,
          fiscal_year: Number(fiscalYear),
          fiscal_quarter: quarter ? Number(quarter) : null,
          period_end: periodEnd || null,
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = Array.isArray(body.detail)
          ? body.detail.map((d: { msg?: string }) => (d.msg || "").replace(/^Value error, /, "")).join("; ")
          : body.detail;
        throw new Error(detail || `HTTP ${res.status}`);
      }
      onSaved(documentId);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không lưu được thông tin tài liệu.");
    } finally {
      setSaving(false);
    }
  };

  const candidates = data?.metadata.name_candidates || [];

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        <div className="auth-header">
          <div>
            <h2 className="auth-title">Thông tin tài liệu</h2>
            <p className="auth-subtitle">{data ? data.file_name : "Đang tải..."}</p>
          </div>
          <button onClick={onClose} className="auth-close-btn" aria-label="Đóng">
            <CloseIcon size={16} />
          </button>
        </div>

        {error && <div className="auth-alert-error">{error}</div>}
        {data?.needs_confirmation && (
          <div className="auth-alert-error" style={{ color: "#b45309", borderColor: "rgba(245, 158, 11, 0.4)", backgroundColor: "rgba(245, 158, 11, 0.08)" }}>
            Hệ thống chưa xác minh được công ty hoặc kỳ báo cáo trong tài liệu. Hãy kiểm tra và xác nhận trước khi hỏi.
          </div>
        )}

        {data && (
          <div className="auth-body">
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="auth-field">
                <label className="auth-label">Tên công ty (pháp nhân)</label>
                <select className="auth-input" value={choice} onChange={(e) => setChoice(e.target.value)} style={flag("entity")}>
                  {candidates.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                      {c.pages.length ? ` (trang ${c.pages.join(", ")})` : ""}
                    </option>
                  ))}
                  <option value={OTHER}>Khác (nhập tay)</option>
                </select>
                {choice === OTHER && (
                  <input
                    className="auth-input"
                    value={typedName}
                    onChange={(e) => setTypedName(e.target.value)}
                    maxLength={120}
                    placeholder="Ví dụ: Advanced Micro Devices, Inc."
                    required
                  />
                )}
              </div>

              <div className="auth-field">
                <label className="auth-label">Mã chứng khoán / tên viết tắt</label>
                <input
                  className="auth-input"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  maxLength={10}
                  pattern="[A-Z0-9.\-]{1,10}"
                  placeholder="Ví dụ: AMD"
                />
              </div>

              <div className="auth-field">
                <label className="auth-label">Tên khác / tên cũ (tối đa 5, cách nhau bằng dấu phẩy)</label>
                <input
                  className="auth-input"
                  value={aliases}
                  onChange={(e) => setAliases(e.target.value)}
                  maxLength={320}
                  placeholder="Ví dụ: Facebook"
                />
              </div>

              <div className="auth-field">
                <label className="auth-label">Loại báo cáo</label>
                <select className="auth-input" value={reportType} onChange={(e) => setReportType(e.target.value)}>
                  {data.report_types.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="auth-field" style={{ display: "flex", gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <label className="auth-label">Năm tài chính</label>
                  <input
                    className="auth-input"
                    type="number"
                    min={1990}
                    max={new Date().getFullYear() + 1}
                    value={fiscalYear}
                    onChange={(e) => setFiscalYear(e.target.value)}
                    style={flag("period_end")}
                    required
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label className="auth-label">Quý</label>
                  <select className="auth-input" value={quarter} onChange={(e) => setQuarter(e.target.value)}>
                    <option value="">Cả năm</option>
                    {[1, 2, 3, 4].map((q) => (
                      <option key={q} value={q}>
                        Q{q}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label">Ngày kết thúc kỳ</label>
                <input
                  className="auth-input"
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  style={flag("period_end")}
                />
              </div>

              <button type="submit" className="auth-submit-btn" disabled={saving}>
                {saving ? "Đang lưu..." : "Xác nhận thông tin"}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
