import React from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import { ThemeToggle } from "../../components/common/ThemeToggle";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import { SignUpForm } from "../../components/auth/SignUpForm";
import "./auth-pages.css";

/** /register: the page around the sign-up form the dialog uses too (components/auth/SignUpForm.tsx). */
export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register } = useAuth();
  const { t } = useLanguage();

  return (
    <div className="auth-page-wrapper">
      <div className="auth-page-card">
        <div className="auth-page-tools">
          <ThemeToggle />
          <LanguageToggle size="sm" />
        </div>

        <Link to="/" className="auth-page-brand">
          <FinHelpLogo size="md" />
        </Link>

        <div className="auth-page-header">
          <h1 className="auth-page-title">{t.auth.createAccountTitle}</h1>
          <p className="auth-page-desc">{t.auth.createAccountDesc}</p>
        </div>

        <SignUpForm
          idPrefix="register"
          onSubmit={async (email, username, password, fullName) => {
            await register(email, username, password, fullName);
            navigate("/app");
          }}
        />

        <div className="auth-page-footer">
          <div>
            {t.auth.haveAccount}{" "}
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
