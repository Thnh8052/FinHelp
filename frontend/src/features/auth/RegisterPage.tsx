import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import "./auth-pages.css";

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const { t } = useLanguage();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 6) {
      setError(t.auth.errorPasswordLength);
      return;
    }

    setLoading(true);

    try {
      await register(email, username, password, fullName || undefined);
      navigate("/app");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : t.auth.errorInvalidCredentials
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-wrapper">
      <div className="auth-page-card" style={{ position: "relative" }}>
        {/* Language Switcher in top-right */}
        <div className="auth-page-lang-toggle">
          <LanguageToggle size="sm" />
        </div>

        {/* Brand */}
        <Link to="/" className="auth-page-brand">
          <span style={{ fontSize: "20px" }}>⚡</span>
          <span className="auth-page-brand-name">FinHelp</span>
        </Link>

        {/* Header */}
        <div className="auth-page-header">
          <h1 className="auth-page-title">{t.auth.createAccountTitle}</h1>
          <p className="auth-page-desc">
            {t.auth.createAccountDesc}
          </p>
        </div>

        {/* Alert */}
        {error && <div className="auth-page-alert auth-page-alert-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-page-form">
          <div className="auth-page-field">
            <label className="auth-page-label">{t.auth.emailAddress}</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="auth-page-input"
            />
          </div>

          <div className="auth-page-field">
            <label className="auth-page-label">{t.auth.username}</label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. analyst_pro"
              className="auth-page-input"
            />
          </div>

          <div className="auth-page-field">
            <label className="auth-page-label">{t.auth.fullNameOptional}</label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Alex Morgan"
              className="auth-page-input"
            />
          </div>

          <div className="auth-page-field">
            <label className="auth-page-label">{t.auth.passwordMin6}</label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="auth-page-input"
            />
          </div>

          <button type="submit" disabled={loading} className="auth-page-btn">
            {loading ? t.auth.creatingAccount : t.auth.completeRegistration}
          </button>
        </form>

        {/* Footer */}
        <div className="auth-page-footer">
          <div>
            {t.auth.haveAccount}{" "}
            <Link to="/login" className="auth-page-link">
              {t.auth.signInNow}
            </Link>
          </div>
          <div>
            <Link to="/" className="auth-page-link" style={{ color: "#6b7280" }}>
              {t.common.backToHome}
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
