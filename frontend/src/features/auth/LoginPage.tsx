import React, { useState, useEffect } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import "./auth-pages.css";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();
  const { t } = useLanguage();

  const urlEmail = searchParams.get("email") || "";
  const [identifier, setIdentifier] = useState(urlEmail);
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (urlEmail) {
      setIdentifier(urlEmail);
    }
  }, [urlEmail]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(identifier, password);
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
          <h1 className="auth-page-title">{t.auth.signInTitle}</h1>
          <p className="auth-page-desc">
            {t.auth.signInDesc}
          </p>
        </div>

        {/* Alert */}
        {error && <div className="auth-page-alert auth-page-alert-error">{error}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} className="auth-page-form">
          <div className="auth-page-field">
            <label className="auth-page-label">{t.auth.emailOrUsername}</label>
            <input
              type="text"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="name@company.com"
              className="auth-page-input"
            />
          </div>

          <div className="auth-page-field">
            <div className="auth-page-row">
              <label className="auth-page-label">{t.auth.password}</label>
              <Link
                to={`/reset-password${identifier ? `?email=${encodeURIComponent(identifier)}` : ""}`}
                className="auth-page-link auth-page-link-small"
              >
                {t.auth.forgotPassword}
              </Link>
            </div>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="auth-page-input"
            />
          </div>

          <button type="submit" disabled={loading} className="auth-page-btn">
            {loading ? t.auth.signingIn : t.auth.signInBtn}
          </button>
        </form>

        {/* Footer */}
        <div className="auth-page-footer">
          <div>
            {t.auth.noAccount}{" "}
            <Link to="/register" className="auth-page-link">
              {t.auth.signUpNow}
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
