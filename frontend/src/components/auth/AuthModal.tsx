import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { authService } from "../../services/auth";
import { CloseIcon, SparklesIcon } from "../common/Icons";
import "./auth.css";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "signin" | "signup";
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, initialTab = "signin" }) => {
  const { login, register, continueAsGuest } = useAuth();
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
  const [otpDebug, setOtpDebug] = useState<string | null>(null);

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
      const res = await authService.forgotPassword(forgotEmail);
      if (res.otp_debug) {
        setOtpDebug(res.otp_debug);
      }
      setSuccessMsg("OTP code generated. Please enter code and your new password below.");
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
        setOtpDebug(null);
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
              {tab === "signin" && "Sign In to FinHelp"}
              {tab === "signup" && "Create New Account"}
              {tab === "forgot" && "Reset Password"}
            </h2>
            <p className="auth-subtitle">
              Enterprise-Grade Financial Statement Intelligence Platform
            </p>
          </div>
          <button onClick={onClose} className="auth-close-btn">
            <CloseIcon size={16} />
          </button>
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
                  <label className="auth-label">Email or Username</label>
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
                    <label className="auth-label">Password</label>
                    <button
                      type="button"
                      onClick={() => setTab("forgot")}
                      className="auth-forgot-link"
                    >
                      Forgot password?
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
                  {loading ? "Authenticating..." : "Sign In"}
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
                    <span>Continue in Guest Trial Mode</span>
                  </button>
                </div>
              </div>

              {/* Bottom Switch */}
              <div className="auth-footer-switch">
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signup");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  Register now
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
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. financial_analyst"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Password <span className="auth-required">*</span> (Minimum 6 characters)
                  </label>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Full Name (Optional)
                  </label>
                  <input
                    type="text"
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
                  {loading ? "Creating account..." : "Complete Registration"}
                </button>
              </form>

              <div className="auth-footer-switch">
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signin");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  Sign in
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
                  {otpDebug && (
                    <div className="auth-otp-debug">
                      Development Demo OTP: <strong>{otpDebug}</strong>
                    </div>
                  )}

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
                      New Password (Minimum 6 characters)
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
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
                    {loading ? "Verifying..." : "Confirm & Reset Password"}
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
                  Back to Sign In
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
