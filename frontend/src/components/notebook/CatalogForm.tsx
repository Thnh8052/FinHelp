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
 * 19/11 (chủ dự án: rõ mục đích hơn): một câu nói thông tin này dùng để làm gì, hai nhóm Công ty / Kỳ báo cáo, gợi ý dưới từng trường,
 * trường chưa đọc chắc từ tài liệu có nhãn chữ "Cần kiểm tra" (trước chỉ có viền màu), nhãn gắn với ô, nút Hủy.
 */
export const CatalogForm: React.FC<CatalogFormProps> = ({ documentId, onClose, onSaved }) => {
  const { t } = useLanguage();
  const c = t.catalog;
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
        const known = candidates.find((x) => x.name === m.company_name);
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
      .catch((err: unknown) => setError(c.loadFailed.replace("{reason}", reason(err, t, c.connectionError))));
  }, [documentId]);

  if (!documentId) return null;

  const unverified = new Set(data?.metadata.catalog_unverified || []);
  /** A field the catalog could not confirm in the document: a word next to its label, not only a coloured border. */
  const check = (field: string) =>
    unverified.has(field) ? (
      <span className="auth-check-tag" title={c.needsCheckWhy}>
        {c.needsCheck}
      </span>
    ) : null;
  const flagged = (field: string) => (unverified.has(field) ? "auth-input needs-check" : "auth-input");
  // the fiscal year field is checked when the period could not be read, or when the year was guessed from the end date and the text names another (B1)
  const yearField = unverified.has("fiscal_year") ? "fiscal_year" : "period_end";

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
      setError(reason(err, t, c.saveFailed));
    } finally {
      setSaving(false);
    }
  };

  const candidates = data?.metadata.name_candidates || [];

  return (
    <div className="modal-backdrop" onClick={onClose} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <div className="auth-card" role="dialog" aria-modal="true" aria-labelledby="catalog-title" onClick={(e) => e.stopPropagation()}>
        <div className="auth-header">
          <div>
            <h2 className="auth-title" id="catalog-title">
              {c.title}
            </h2>
            <p className="auth-subtitle">{data ? data.file_name : t.common.loading}</p>
          </div>
          <button type="button" onClick={onClose} className="auth-close-btn" aria-label={t.common.close}>
            <CloseIcon size={16} />
          </button>
        </div>

        <p className="auth-intro">{c.purpose}</p>
        {error && (
          <div className="auth-alert-error" role="alert">
            {error}
          </div>
        )}
        {data?.needs_confirmation && <div className="auth-alert-warning">{c.confirmNotice}</div>}

        {data && (
          <div className="auth-body">
            <form onSubmit={handleSubmit} className="auth-form">
              <fieldset className="auth-fieldset">
                <legend className="auth-legend">{c.companySection}</legend>
                <div className="auth-field">
                  <label className="auth-label" htmlFor="catalog-company">
                    {c.companyName} <span className="auth-required">*</span>
                    {check("entity")}
                  </label>
                  <select id="catalog-company" className={flagged("entity")} value={choice} onChange={(e) => setChoice(e.target.value)}
                          aria-describedby="catalog-company-hint">
                    {candidates.map((x) => (
                      <option key={x.name} value={x.name}>
                        {x.name}
                        {x.pages.length ? ` ${c.pageRef.replace("{pages}", x.pages.join(", "))}` : ""}
                      </option>
                    ))}
                    <option value={OTHER}>{c.otherCompany}</option>
                  </select>
                  {choice === OTHER && (
                    <input className="auth-input" value={typedName} onChange={(e) => setTypedName(e.target.value)} maxLength={120}
                           placeholder={c.exampleCompany} aria-label={c.companyName} required style={{ marginTop: 6 }} />
                  )}
                  <p id="catalog-company-hint" className="auth-field-hint">
                    {c.companyHint}
                  </p>
                </div>

                <div className="auth-field-row">
                  <div className="auth-field auth-field-col">
                    <label className="auth-label" htmlFor="catalog-ticker">
                      {c.ticker}
                    </label>
                    <input id="catalog-ticker" className="auth-input" value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} maxLength={10}
                           pattern="[A-Z0-9.\-]{1,10}" placeholder={c.exampleTicker} aria-describedby="catalog-ticker-hint" />
                  </div>
                  <div className="auth-field auth-field-col">
                    <label className="auth-label" htmlFor="catalog-aliases">
                      {c.aliases}
                    </label>
                    <input id="catalog-aliases" className="auth-input" value={aliases} onChange={(e) => setAliases(e.target.value)} maxLength={320}
                           placeholder={c.exampleAlias} aria-describedby="catalog-aliases-hint" />
                  </div>
                </div>
                <p id="catalog-ticker-hint" className="auth-field-hint">
                  {c.tickerHint}
                </p>
                <p id="catalog-aliases-hint" className="auth-field-hint">
                  {c.aliasesHint}
                </p>
              </fieldset>

              <fieldset className="auth-fieldset">
                <legend className="auth-legend">{c.periodSection}</legend>
                <div className="auth-field">
                  <label className="auth-label" htmlFor="catalog-report-type">
                    {c.reportType}
                  </label>
                  <select id="catalog-report-type" className="auth-input" value={reportType} onChange={(e) => setReportType(e.target.value)}>
                    {data.report_types.map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="auth-field-row">
                  <div className="auth-field auth-field-col">
                    <label className="auth-label" htmlFor="catalog-year">
                      {c.fiscalYear} <span className="auth-required">*</span>
                      {check(yearField)}
                    </label>
                    <input id="catalog-year" className={flagged(yearField)} type="number" min={1990} max={new Date().getFullYear() + 1}
                           value={fiscalYear} onChange={(e) => setFiscalYear(e.target.value)} required aria-describedby="catalog-period-hint" />
                  </div>
                  <div className="auth-field auth-field-col">
                    <label className="auth-label" htmlFor="catalog-quarter">
                      {c.quarter}
                    </label>
                    <select id="catalog-quarter" className="auth-input" value={quarter} onChange={(e) => setQuarter(e.target.value)}>
                      <option value="">{c.fullYear}</option>
                      {[1, 2, 3, 4].map((q) => (
                        <option key={q} value={q}>
                          Q{q}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="auth-field">
                  <label className="auth-label" htmlFor="catalog-period-end">
                    {c.periodEnd}
                    {check("period_end")}
                  </label>
                  <input id="catalog-period-end" className={flagged("period_end")} type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)}
                         aria-describedby="catalog-period-hint" />
                  <p id="catalog-period-hint" className="auth-field-hint">
                    {c.periodHint}
                  </p>
                </div>
              </fieldset>

              <div className="auth-actions">
                <button type="button" className="auth-secondary-btn" onClick={onClose}>
                  {t.common.cancel}
                </button>
                <button type="submit" className="auth-submit-btn" disabled={saving}>
                  {saving ? c.saving : c.confirm}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
