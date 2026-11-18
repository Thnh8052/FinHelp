import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../common/LanguageToggle";
import { ThemeToggle } from "../common/ThemeToggle";
import { UserDropdown } from "../auth/UserDropdown";
import { ChevronRightIcon, MenuIcon, UserIcon } from "../common/Icons";
import "./layout.css";

interface NavbarProps {
  notebookTitle: string;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  onOpenAuthModal: () => void;
}

/** The top bar of the work area: sidebar button, "Workspace › chat title", theme, language, account. */
export const Navbar: React.FC<NavbarProps> = ({
  notebookTitle,
  isSidebarOpen = true,
  onToggleSidebar,
  onOpenAuthModal,
}) => {
  const { user } = useAuth();
  const { t } = useLanguage();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Get initials for avatar (e.g. "VT" for Vũ Thành)
  const getInitials = (name?: string | null) => {
    if (!name) return "U";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
  };

  const isAdmin = user?.role === "admin";
  const title = notebookTitle || t.nav.defaultTitle;

  return (
    <header className="navbar">
      <div className="navbar-crumb-box">
        {onToggleSidebar && (
          <button
            type="button"
            id="btn-toggle-sidebar"
            onClick={onToggleSidebar}
            className={`navbar-sidebar-btn ${isSidebarOpen ? "active" : ""}`}
            title={t.nav.toggleSidebar}
            aria-label={t.nav.toggleSidebar}
            aria-expanded={isSidebarOpen}
          >
            <MenuIcon size={16} />
          </button>
        )}
        <div className="navbar-crumb">
          <span className="navbar-crumb-root">{t.nav.breadcrumbRoot}</span>
          <ChevronRightIcon size={14} />
          <h1 className="navbar-crumb-title" title={title}>{title}</h1>
        </div>
        {!user && <span className="navbar-session-note">{t.nav.sessionOnly}</span>}
      </div>

      <div className="navbar-actions">
        <ThemeToggle />
        <LanguageToggle size="sm" />

        {user ? (
          <div
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="navbar-user-chip"
            title={user.full_name || user.username}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setDropdownOpen(!dropdownOpen);
            }}
          >
            <div className={`navbar-avatar ${isAdmin ? "admin" : ""}`}>
              {getInitials(user.full_name || user.username)}
            </div>
            <span className="navbar-username">
              {user.full_name ? user.full_name.split(" - ")[0] : user.username}
            </span>
            <span className={`navbar-role-badge ${isAdmin ? "admin" : ""}`}>
              {isAdmin ? t.nav.roleAdmin : t.nav.roleUser}
            </span>
          </div>
        ) : (
          // The guest's sign-in lives in the sidebar card; with the sidebar closed this button keeps it one click away
          !isSidebarOpen && (
            <button type="button" onClick={onOpenAuthModal} className="navbar-login-btn">
              <UserIcon size={12} />
              <span>{t.common.signIn}</span>
            </button>
          )
        )}

        {/* Dropdown Popover */}
        <UserDropdown
          isOpen={dropdownOpen}
          onClose={() => setDropdownOpen(false)}
          onOpenAuthModal={onOpenAuthModal}
        />
      </div>
    </header>
  );
};
