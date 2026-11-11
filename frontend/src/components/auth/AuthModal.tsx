import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { authService } from "../../services/auth";
import { LanguageToggle } from "../common/LanguageToggle";
import { CloseIcon, SparklesIcon } from "../common/Icons";
import "./auth.css";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "signin" | "signup";
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, initialTab = "signin" }) => {
  const { login, register, continueAsGuest } = useAuth();
  const { t, lang } = useLanguage();
  const [tab, setTab] = useState<"signin" | "signup" | "forgot">(initialTab);

  // Form states
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");

  // Forgot password states
  const [forgotStep, setForgotStep] = useState<1 | 2>(1);
  const [forgotEmail, setForgotEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign in failed. Please verify your credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, username, password, fullName);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed. Email or username may already exist.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authService.forgotPassword(forgotEmail);
      setSuccessMsg("If the email is registered, a verification code has been sent. Enter it with your new password below.");
      setForgotStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to send OTP code.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotStep2 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authService.resetPassword(forgotEmail, otpCode, newPassword);
      setSuccessMsg(res.message);
      setTimeout(() => {
        setTab("signin");
        setForgotStep(1);
        setSuccessMsg(null);
      }, 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "OTP verification failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="auth-header">
          <div>
            <h2 className="auth-title">
              {tab === "signin" && t.auth.signInTitle}
              {tab === "signup" && t.auth.createAccountTitle}
              {tab === "forgot" && t.auth.resetPasswordTitle}
            </h2>
            <p className="auth-subtitle">
              {tab === "signin" && t.auth.signInDesc}
              {tab === "signup" && t.auth.createAccountDesc}
              {tab === "forgot" && t.auth.forgotStep1Desc}
            </p>
          </div>
          <div className="auth-header-actions">
            <LanguageToggle size="sm" />
            <button onClick={onClose} className="auth-close-btn" aria-label="Close">
              <CloseIcon size={16} />
            </button>
          </div>
        </div>

        {/* Alerts */}
        {error && <div className="auth-alert-error">{error}</div>}
        {successMsg && <div className="auth-alert-success">{successMsg}</div>}

        <div className="auth-body">
          {/* TAB 1: SIGN IN */}
          {tab === "signin" && (
            <div>
              <form onSubmit={handleSignIn} className="auth-form">
                <div className="auth-field">
                  <label className="auth-label">{t.auth.emailOrUsername}</label>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="user@finhelp.ai"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <div className="auth-label-row">
                    <label className="auth-label">{t.auth.password}</label>
                    <button
                      type="button"
                      onClick={() => setTab("forgot")}
                      className="auth-forgot-link"
                    >
                      {t.auth.forgotPassword}
                    </button>
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="auth-submit-btn"
                >
                  {loading ? t.auth.signingIn : t.auth.signInBtn}
                </button>
              </form>

              <div className="auth-guest-section">
                {/* Guest Preview */}
                <div className="auth-guest-box">
                  <button
                    type="button"
                    onClick={() => {
                      continueAsGuest();
                      onClose();
                    }}
                    className="auth-guest-link"
                  >
                    <SparklesIcon size={12} />
                    <span>{t.auth.continueAsGuest}</span>
                  </button>
                </div>
              </div>

              {/* Bottom Switch */}
              <div className="auth-footer-switch">
                {t.auth.noAccount}{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signup");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  {t.auth.signUpNow}
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: SIGN UP */}
          {tab === "signup" && (
            <div>
              <form onSubmit={handleSignUp} className="auth-form-dense">
                <div className="auth-field">
                  <label className="auth-label">
                    Email <span className="auth-required">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@company.com"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Username <span className="auth-required">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    pattern="[A-Za-z0-9._\-]{3,32}"
                    title={t.auth.usernameRule}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. financial_analyst"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    {t.auth.passwordMin} <span className="auth-required">*</span>
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    {t.auth.fullNameOptional}
                  </label>
                  <input
                    type="text"
                    maxLength={120}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. John Doe"
                    className="auth-input"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="auth-submit-btn spaced"
                >
                  {loading ? t.auth.creatingAccount : t.auth.completeRegistration}
                </button>
              </form>

              <div className="auth-footer-switch">
                {t.auth.haveAccount}{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signin");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  {t.auth.signInNow}
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: FORGOT PASSWORD */}
          {tab === "forgot" && (
            <div>
              {forgotStep === 1 ? (
                <form onSubmit={handleForgotStep1} className="auth-form">
                  <p className="auth-hint-text">
                    Enter your registered email address to receive a 6-digit OTP verification code (valid for 15 minutes):
                  </p>
                  <div>
                    <input
                      type="email"
                      required
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      placeholder="email@example.com"
                      className="auth-input"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="auth-submit-btn"
                  >
                    {loading ? "Sending..." : "Send OTP Code"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleForgotStep2} className="auth-form">
                  <div className="auth-field">
                    <label className="auth-label">
                      OTP Code (6 digits)
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      placeholder="123456"
                      className="auth-input"
                    />
                  </div>

                  <div className="auth-field">
                    <label className="auth-label">
                      {t.auth.newPasswordMin}
                    </label>
                    <input
                      type="password"
                      required
                      minLength={8}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      className="auth-input"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="auth-submit-btn"
                  >
                    {loading ? t.auth.verifying : t.auth.resetSubmit}
                  </button>
                </form>
              )}

              <div className="auth-footer-switch">
                <button
                  type="button"
                  onClick={() => {
                    setTab("signin");
                    setError(null);
                    setSuccessMsg(null);
                  }}
                  className="auth-link-btn secondary"
                >
                  {lang === "vi" ? "← Quay lại Đăng nhập" : "← Back to Sign In"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
