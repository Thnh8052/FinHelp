import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { authService } from "../../services/auth";
import { errorText } from "../../services/api";
import { LanguageToggle } from "../common/LanguageToggle";
import { ThemeToggle } from "../common/ThemeToggle";
import { CloseIcon, SparklesIcon } from "../common/Icons";
import { SignUpForm } from "./SignUpForm";
import "./auth.css";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "signin" | "signup";
}

/** The dialog lives only while it is open: closing it drops what was typed, so a password typed before signing out is not waiting in the next
 * dialog, and it opens again on its first tab (auth flow test 19/11). */
export const AuthModal: React.FC<AuthModalProps> = (props) => (props.isOpen ? <AuthDialog {...props} /> : null);

const AuthDialog: React.FC<AuthModalProps> = ({ onClose, initialTab = "signin" }) => {
  const { login, register, continueAsGuest } = useAuth();
  const { t } = useLanguage();
  const [tab, setTab] = useState<"signin" | "signup" | "forgot">(initialTab);

  // Form states
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");

  // Forgot password states
  const [forgotStep, setForgotStep] = useState<1 | 2>(1);
  const [forgotEmail, setForgotEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
      onClose();
    } catch (err: unknown) {
      setError(errorText(err, t, t.auth.errorSignInFallback));
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
      setSuccessMsg(t.auth.codeSentGeneric);
      setForgotStep(2);
    } catch (err: unknown) {
      setError(errorText(err, t, t.auth.errorSendOtpFallback));
    } finally {
      setLoading(false);
    }
  };

  const handleForgotStep2 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authService.resetPassword(forgotEmail, otpCode, newPassword);
      setSuccessMsg(t.auth.passwordResetSuccess);
      setTimeout(() => {
        setTab("signin");
        setForgotStep(1);
        setSuccessMsg(null);
      }, 1500);
    } catch (err: unknown) {
      setError(errorText(err, t, t.auth.errorOtpFallback));
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
            <ThemeToggle />
            <LanguageToggle size="sm" />
            <button onClick={onClose} className="auth-close-btn" aria-label={t.common.close}>
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
                  <label className="auth-label" htmlFor="modal-identifier">{t.auth.emailOrUsername}</label>
                  <input
                    id="modal-identifier"
                    autoComplete="username"
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
                    <label className="auth-label" htmlFor="modal-password">{t.auth.password}</label>
                    <button
                      type="button"
                      onClick={() => setTab("forgot")}
                      className="auth-forgot-link"
                    >
                      {t.auth.forgotPassword}
                    </button>
                  </div>
                  <input
                    id="modal-password"
                    autoComplete="current-password"
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
              <SignUpForm
                idPrefix="modal-reg"
                onSubmit={async (email, username, password, fullName) => {
                  await register(email, username, password, fullName);
                  onClose();
                }}
              />

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
                    {t.auth.forgotHint}
                  </p>
                  <div>
                    <input
                      type="email"
                      autoComplete="email"
                      aria-label={t.auth.accountEmail}
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
                    {loading ? t.auth.sendingCode : t.auth.sendCodeBtn}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleForgotStep2} className="auth-form">
                  <div className="auth-field">
                    <label className="auth-label" htmlFor="modal-otp">
                      {t.auth.otpCode}
                    </label>
                    <input
                      id="modal-otp"
                      autoComplete="one-time-code"
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
                    <label className="auth-label" htmlFor="modal-new-password">
                      {t.auth.newPasswordMin}
                    </label>
                    <input
                      id="modal-new-password"
                      autoComplete="new-password"
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
                  {t.auth.backToSignIn}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
