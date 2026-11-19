import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { errorText } from "../../services/api";
import { authService } from "../../services/auth";
import { CloseIcon } from "../common/Icons";
import { MIN_PASSWORD, passwordChangeProblem } from "./passwordChange";
import "./auth.css";

interface ChangePasswordDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

/** Lives only while open, like the sign-in dialog: closing it drops the passwords typed into it. */
export const ChangePasswordDialog: React.FC<ChangePasswordDialogProps> = (props) => (props.isOpen ? <ChangePasswordBody {...props} /> : null);

const ChangePasswordBody: React.FC<ChangePasswordDialogProps> = ({ onClose }) => {
  const { t } = useLanguage();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = passwordChangeProblem(current, next, confirm);
    if (problem) {
      setError(t.account[problem]);
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await authService.changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      setDone(true);
    } catch (err: unknown) {
      setError(errorText(err, t, t.account.failed));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} onKeyDown={(e) => e.key === "Escape" && onClose()}>
      <div className="auth-card" role="dialog" aria-modal="true" aria-labelledby="change-password-title" onClick={(e) => e.stopPropagation()}>
        <div className="auth-header">
          <div>
            <h2 className="auth-title" id="change-password-title">{t.account.title}</h2>
            <p className="auth-subtitle">{done ? t.account.done : t.account.desc}</p>
          </div>
          <div className="auth-header-actions">
            <button type="button" onClick={onClose} className="auth-close-btn" aria-label={t.common.close}>
              <CloseIcon size={16} />
            </button>
          </div>
        </div>

        {error && <div className="auth-alert-error" role="alert">{error}</div>}
        {done && <div className="auth-alert-success" role="status">{t.account.doneDesc}</div>}

        <div className="auth-body">
          {done ? (
            <div className="auth-form">
              <button type="button" className="auth-submit-btn" onClick={onClose} autoFocus>
                {t.account.close}
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="auth-form" noValidate>
              <div className="auth-field">
                <label className="auth-label" htmlFor="change-current">{t.account.currentPassword}</label>
                <input id="change-current" type="password" autoComplete="current-password" className="auth-input" autoFocus
                       value={current} onChange={(e) => setCurrent(e.target.value)} />
              </div>
              <div className="auth-field">
                <label className="auth-label" htmlFor="change-new">{t.account.newPassword}</label>
                <input id="change-new" type="password" autoComplete="new-password" className="auth-input" minLength={MIN_PASSWORD}
                       aria-describedby="change-new-hint" value={next} onChange={(e) => setNext(e.target.value)} />
                <p className="auth-hint-text" id="change-new-hint">{t.account.hint}</p>
              </div>
              <div className="auth-field">
                <label className="auth-label" htmlFor="change-confirm">{t.account.confirmPassword}</label>
                <input id="change-confirm" type="password" autoComplete="new-password" className="auth-input"
                       value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </div>
              <button type="submit" disabled={saving} className="auth-submit-btn">
                {saving ? t.account.saving : t.account.save}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
