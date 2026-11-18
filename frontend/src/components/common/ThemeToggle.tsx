import React from "react";
import { Moon, Sun } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { useTheme } from "../../context/ThemeContext";

/** One round button: shows the theme you would switch TO, and says so to screen readers. */
export const ThemeToggle: React.FC<{ className?: string }> = ({ className = "" }) => {
  const { t } = useLanguage();
  const { theme, toggleTheme } = useTheme();
  const label = theme === "dark" ? t.common.switchToLight : t.common.switchToDark;
  return (
    <button type="button" onClick={toggleTheme} className={`theme-toggle ${className}`} title={label} aria-label={label}>
      {theme === "dark" ? <Sun size={16} aria-hidden /> : <Moon size={16} aria-hidden />}
    </button>
  );
};
