import React from "react";
import { useLanguage } from "../../context/LanguageContext";
import "./LanguageToggle.css";

interface LanguageToggleProps {
  className?: string;
  size?: "sm" | "md";
}

export const LanguageToggle: React.FC<LanguageToggleProps> = ({
  className = "",
  size = "md",
}) => {
  const { lang, setLang } = useLanguage();

  return (
    <div
      className={`lang-toggle-group ${size === "sm" ? "lang-toggle-sm" : ""} ${className}`}
      role="group"
      aria-label="Language selection"
    >
      <button
        type="button"
        onClick={() => setLang("en")}
        className={`lang-toggle-item ${lang === "en" ? "active" : ""}`}
        title="English"
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLang("vi")}
        className={`lang-toggle-item ${lang === "vi" ? "active" : ""}`}
        title="Tiếng Việt"
      >
        VI
      </button>
    </div>
  );
};

