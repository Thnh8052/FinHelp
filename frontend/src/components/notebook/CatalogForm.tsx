import React, { useEffect, useState } from "react";
import { CloseIcon } from "../common/Icons";
import { useLanguage } from "../../context/LanguageContext";
import type { TranslationSchema } from "../../locales/types";
import { ApiError, errorText, fieldErrorText } from "../../services/api";
import { documentService } from "../../services/documents";
import { CatalogPayload } from "../../types/notebook";
import "../auth/auth.css";

/** The reason in words: each refused field of the form (named by its code), else the sentence for the error. */
const reason = (err: unknown, t: TranslationSchema, fallback: string): string =>
  err instanceof ApiError && err.fields.length ? err.fields.map((f) => fieldErrorText(f, t)).join("; ") : errorText(err, t, fallback);

interface CatalogFormProps {
  documentId: string | null;
  onClose: () => void;
  onSaved: (documentId: string) => void;
}

const OTHER = "__other__";

/**
 * Mẫu xác nhận danh tính tài liệu: tên công ty chọn từ các tên tìm được trong tài liệu (kèm trang), chỉ gõ tay khi không có
 * tên đúng; mã CK, tên khác, loại báo cáo, năm / quý, ngày kết thúc kỳ. Backend kiểm lại mọi trường (422 khi sai dạng).
 */
export const CatalogForm: React.FC<CatalogFormProps> = ({ documentId, onClose, onSaved }) => {
  const { t } = useLanguage();
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
    documentService
      .getCatalog(documentId)
      .then((d) => {
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
      .catch((err: unknown) => setError(t.catalog.loadFailed.replace("{reason}", reason(err, t, t.catalog.connectionError))));
  }, [documentId]);

  if (!documentId) return null;

  const unverified = new Set(data?.metadata.catalog_unverified || []);
  const flag = (field: string) => (unverified.has(field) ? { borderColor: "#f59e0b" } : undefined);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await documentService.updateCatalog(documentId, {
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
      });
      onSaved(documentId);
      onClose();
    } catch (err: unknown) {
      setError(reason(err, t, t.catalog.saveFailed));
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
            <h2 className="auth-title">{t.catalog.title}</h2>
            <p className="auth-subtitle">{data ? data.file_name : "Loading..."}</p>
          </div>
          <button onClick={onClose} className="auth-close-btn" aria-label={t.common.close}>
            <CloseIcon size={16} />
          </button>
        </div>

        {error && <div className="auth-alert-error">{error}</div>}
        {data?.needs_confirmation && (
          <div className="auth-alert-warning">
            {t.catalog.confirmNotice}
          </div>
        )}

        {data && (
          <div className="auth-body">
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="auth-field">
                <label className="auth-label">{t.catalog.companyName}</label>
                <select className="auth-input" value={choice} onChange={(e) => setChoice(e.target.value)} style={flag("entity")}>
                  {candidates.map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                      {c.pages.length ? ` ${t.catalog.pageRef.replace("{pages}", c.pages.join(", "))}` : ""}
                    </option>
                  ))}
                  <option value={OTHER}>{t.catalog.otherCompany}</option>
                </select>
                {choice === OTHER && (
                  <input
                    className="auth-input"
                    value={typedName}
                    onChange={(e) => setTypedName(e.target.value)}
                    maxLength={120}
                    placeholder={t.catalog.exampleCompany}
                    required
                  />
                )}
              </div>

              <div className="auth-field">
                <label className="auth-label">{t.catalog.ticker}</label>
                <input
                  className="auth-input"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  maxLength={10}
                  pattern="[A-Z0-9.\-]{1,10}"
                  placeholder={t.catalog.exampleTicker}
                />
              </div>

              <div className="auth-field">
                <label className="auth-label">{t.catalog.aliases}</label>
                <input
                  className="auth-input"
                  value={aliases}
                  onChange={(e) => setAliases(e.target.value)}
                  maxLength={320}
                  placeholder={t.catalog.exampleAlias}
                />
              </div>

              <div className="auth-field">
                <label className="auth-label">{t.catalog.reportType}</label>
                <select className="auth-input" value={reportType} onChange={(e) => setReportType(e.target.value)}>
                  {data.report_types.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="auth-field auth-field-row">
                <div className="auth-field-col">
                  <label className="auth-label">{t.catalog.fiscalYear}</label>
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
                <div className="auth-field-col">
                  <label className="auth-label">{t.catalog.quarter}</label>
                  <select className="auth-input" value={quarter} onChange={(e) => setQuarter(e.target.value)}>
                    <option value="">{t.catalog.fullYear}</option>
                    {[1, 2, 3, 4].map((q) => (
                      <option key={q} value={q}>
                        Q{q}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label">{t.catalog.periodEnd}</label>
                <input
                  className="auth-input"
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  style={flag("period_end")}
                />
              </div>

              <button type="submit" className="auth-submit-btn" disabled={saving}>
                {saving ? t.catalog.saving : t.catalog.confirm}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
