import React, { useState } from "react";
import { Check, Eye, EyeOff } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { errorText } from "../../services/api";
import { passwordChecks, signUpProblems } from "./signUpRules";
import type { SignUpField, SignUpProblem } from "./signUpRules";
import "./auth.css";

interface SignUpFormProps {
  /** Distinguishes the field ids when the dialog and the page could both be in the document. */
  idPrefix: string;
  onSubmit: (email: string, username: string, password: string, fullName?: string) => Promise<void>;
}

/** The one sign-up form of the dialog and the /register page: what an account is for, a hint and an error in the app's language under each field
 * (the browser's own tooltips spoke the browser's language), a password that can be shown, and a live check of its length. */
export const SignUpForm: React.FC<SignUpFormProps> = ({ idPrefix, onSubmit }) => {
  const { t } = useLanguage();
  const a = t.auth;
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [problems, setProblems] = useState<Partial<Record<SignUpField, SignUpProblem>>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const id = (field: string) => `${idPrefix}-${field}`;
  const message: Record<SignUpProblem, string> = {
    emailMissing: a.emailMissing,
    emailInvalid: a.emailInvalid,
    usernameMissing: a.usernameMissing,
    usernameRule: a.usernameRule,
    passwordMissing: a.passwordMissing,
    passwordShort: a.errorPasswordLength,
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const found = signUpProblems({ email, username, password });
    setProblems(found);
    setError(null);
    const first = (["email", "username", "password"] as SignUpField[]).find((f) => found[f]);
    if (first) {
      document.getElementById(id(first))?.focus();
      return;
    }
    setLoading(true);
    try {
      await onSubmit(email.trim(), username.trim(), password, fullName.trim() || undefined);
    } catch (err: unknown) {
      setError(errorText(err, t, a.errorRegisterFallback));
    } finally {
      setLoading(false);
    }
  };

  /** aria-describedby: the hint, then the error when there is one */
  const described = (field: SignUpField, hint: boolean) => [hint ? id(`${field}-hint`) : "", problems[field] ? id(`${field}-error`) : ""].filter(Boolean).join(" ") || undefined;
  const fieldError = (field: SignUpField) =>
    problems[field] ? (
      <p id={id(`${field}-error`)} className="auth-field-error">
        {message[problems[field]!]}
      </p>
    ) : null;
  const length = passwordChecks(password).length;

  return (
    <form onSubmit={submit} className="auth-form-dense" noValidate>
      <div className="auth-benefits">
        {a.signUpWhy}
        <ul>
          <li>{a.benefitSave}</li>
          <li>{a.benefitMore}</li>
          <li>{a.benefitRecover}</li>
        </ul>
      </div>

      {error && (
        <div role="alert" className="auth-alert-error auth-alert-inline">
          {error}
        </div>
      )}

      <div className="auth-field">
        <label className="auth-label" htmlFor={id("full-name")}>
          {a.fullNameOptional}
        </label>
        <input id={id("full-name")} autoComplete="name" type="text" maxLength={120} value={fullName} onChange={(e) => setFullName(e.target.value)}
               placeholder={a.exampleName} className="auth-input" />
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor={id("email")}>
          {a.emailAddress} <span className="auth-required">*</span>
        </label>
        <input id={id("email")} autoComplete="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com"
               className="auth-input" aria-required="true" aria-invalid={!!problems.email} aria-describedby={described("email", true)} />
        <p id={id("email-hint")} className="auth-field-hint">
          {a.emailHint}
        </p>
        {fieldError("email")}
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor={id("username")}>
          {a.username} <span className="auth-required">*</span>
        </label>
        <input id={id("username")} autoComplete="username" type="text" maxLength={32} value={username} onChange={(e) => setUsername(e.target.value)}
               placeholder={a.exampleUsername} className="auth-input" aria-required="true" aria-invalid={!!problems.username}
               aria-describedby={described("username", !problems.username)} />
        {!problems.username && (
          <p id={id("username-hint")} className="auth-field-hint">
            {a.usernameRule}
          </p>
        )}
        {fieldError("username")}
      </div>

      <div className="auth-field">
        <label className="auth-label" htmlFor={id("password")}>
          {a.password} <span className="auth-required">*</span>
        </label>
        <div className="auth-password-wrap">
          <input id={id("password")} autoComplete="new-password" type={showPassword ? "text" : "password"} value={password}
                 onChange={(e) => setPassword(e.target.value)} className="auth-input" aria-required="true" aria-invalid={!!problems.password}
                 aria-describedby={described("password", true)} />
          <button type="button" className="auth-password-toggle" onClick={() => setShowPassword((v) => !v)} aria-pressed={showPassword}
                  aria-label={showPassword ? a.hidePassword : a.showPassword} aria-controls={id("password")}>
            {showPassword ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
          </button>
        </div>
        <p id={id("password-hint")} className={`auth-checklist${length ? " met" : ""}`}>
          <Check size={13} aria-hidden style={{ opacity: length ? 1 : 0.35 }} />
          {a.passwordRuleLength}
        </p>
        {fieldError("password")}
      </div>

      <button type="submit" disabled={loading} className="auth-submit-btn spaced">
        {loading ? a.creatingAccount : a.completeRegistration}
      </button>
    </form>
  );
};
