import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { authService } from "../../services/auth";
import { errorText } from "../../services/api";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import "./auth-pages.css";

export const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useLanguage();

  const urlEmail = searchParams.get("email") || "";

  // Step 1: Request OTP, Step 2: Set New Password (the link in the email: the code is typed from the email, it is never in the address)
  const [step, setStep] = useState<1 | 2>(urlEmail ? 2 : 1);
  const [email, setEmail] = useState(urlEmail);
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (urlEmail) {
      setEmail(urlEmail);
      setStep(2);
    }
  }, [urlEmail]);

  // Step 1: Send OTP
  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authService.forgotPassword(email);
      setSuccess(t.auth.codeSentSuccess);
      setStep(2);
    } catch (err: unknown) {
      setError(errorText(err, t, t.auth.errorInvalidCredentials));
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Confirm OTP & New Password
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError(t.auth.errorPasswordLength);
      return;
    }

    if (newPassword !== confirmPassword) {
      setError(t.auth.errorPasswordMismatch);
      return;
    }

    setLoading(true);
    try {
      await authService.resetPassword(email, otpCode.trim(), newPassword);
      setSuccess(t.auth.passwordResetSuccess);
      setTimeout(() => {
        navigate(`/login?email=${encodeURIComponent(email)}`);
      }, 1800);
    } catch (err: unknown) {
      setError(errorText(err, t, t.auth.errorOtpInvalid));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-wrapper">
      <div className="auth-page-card">
        {/* Language Switcher in top-right */}
        <div className="auth-page-lang-toggle">
          <LanguageToggle size="sm" />
        </div>

        {/* Brand */}
        <Link to="/" className="auth-page-brand">
          <FinHelpLogo size="sm" showText={false} />
          <span className="auth-page-brand-name">FinHelp</span>
        </Link>

        {/* Header */}
        <div className="auth-page-header">
          <h1 className="auth-page-title">
            {step === 1 ? t.auth.forgotPasswordTitle : t.auth.resetPasswordTitle}
          </h1>
          <p className="auth-page-desc">
            {step === 1
              ? t.auth.forgotStep1Desc
              : `${t.auth.forgotStep2Desc} (${email || ""})`}
          </p>
        </div>

        {/* Alerts */}
        {error && <div className="auth-page-alert auth-page-alert-error">{error}</div>}
        {success && <div className="auth-page-alert auth-page-alert-success">{success}</div>}

        {/* Step 1 Form */}
        {step === 1 && (
          <form onSubmit={handleSendOtp} className="auth-page-form">
            <div className="auth-page-field">
              <label className="auth-page-label">{t.auth.accountEmail}</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="auth-page-input"
              />
            </div>

            <button type="submit" disabled={loading} className="auth-page-btn">
              {loading ? t.auth.sendingCode : t.auth.sendCodeBtn}
            </button>
          </form>
        )}

        {/* Step 2 Form */}
        {step === 2 && (
          <form onSubmit={handleResetPassword} className="auth-page-form">
            <div className="auth-page-field">
              <label className="auth-page-label">{t.auth.accountEmail}</label>
              <input
                type="email"
                disabled
                value={email}
                className="auth-page-input"
              />
            </div>

            <div className="auth-page-field">
              <label className="auth-page-label">{t.auth.otpCode}</label>
              <input
                type="text"
                required
                maxLength={6}
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value)}
                placeholder="123456"
                className="auth-page-input auth-page-input-mono"
              />
            </div>

            <div className="auth-page-field">
              <label className="auth-page-label">{t.auth.newPassword}</label>
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="••••••••"
                className="auth-page-input"
              />
            </div>

            <div className="auth-page-field">
              <label className="auth-page-label">{t.auth.confirmNewPassword}</label>
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                className="auth-page-input"
              />
            </div>

            <button type="submit" disabled={loading} className="auth-page-btn">
              {loading ? t.auth.updatingPassword : t.auth.updatePasswordBtn}
            </button>

            <button
              type="button"
              onClick={() => {
                setStep(1);
                setError(null);
              }}
              className="auth-page-text-btn"
            >
              {t.auth.resendCode}
            </button>
          </form>
        )}

        {/* Footer */}
        <div className="auth-page-footer">
          <div>
            {t.auth.rememberPassword}{" "}
            <Link to="/login" className="auth-page-link">
              {t.auth.signInNow}
            </Link>
          </div>
          <div>
            <Link to="/" className="auth-page-link auth-page-link-muted">
              {t.common.backToHome}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
