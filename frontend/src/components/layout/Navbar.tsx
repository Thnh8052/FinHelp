import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../common/LanguageToggle";
import { UserDropdown } from "../auth/UserDropdown";
import { FileTextIcon, MenuIcon, TableIcon, UserIcon } from "../common/Icons";
import { FinHelpLogo } from "../common/FinHelpLogo";
import "./layout.css";

interface NavbarProps {
  notebookTitle: string;
  sourcesCount?: number;
  isSourcesOpen?: boolean;
  onToggleSources?: () => void;
  isSplitViewOpen?: boolean;
  onToggleSplitView?: () => void;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
  onOpenAuthModal: () => void;
  onNavigateHome?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  notebookTitle,
  sourcesCount = 0,
  isSourcesOpen = false,
  onToggleSources,
  isSplitViewOpen = false,
  onToggleSplitView,
  isSidebarOpen = true,
  onToggleSidebar,
  onOpenAuthModal,
  onNavigateHome,
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

  return (
    <header className="navbar">
      {/* Left: App Logo & Workspace Title */}
      <div className="navbar-brand">
        {onToggleSidebar && (
          <button
            type="button"
            id="btn-toggle-sidebar"
            onClick={onToggleSidebar}
            className={`navbar-sidebar-btn ${isSidebarOpen ? "active" : ""}`}
            title={t.nav.toggleSidebar}
            aria-label={t.nav.toggleSidebar}
          >
            <MenuIcon size={16} />
          </button>
        )}
        <button type="button" className="navbar-brand-home" onClick={onNavigateHome} title={t.nav.returnHome} aria-label={t.nav.returnHome}>
          <FinHelpLogo size="sm" showText={false} />
        </button>
        <div className="navbar-brand-info">
          <div className="navbar-brand-row">
            <span
              className="navbar-brand-title cursor-pointer hover:text-blue-400 transition-colors"
              onClick={onNavigateHome}
              title={t.nav.returnHome}
            >
              FinHelp
            </span>
            <span className="navbar-version-badge">V3</span>
          </div>
          <div className="navbar-brand-subtitle">
            <span className="navbar-status-dot" />
            <span className="navbar-notebook-title" title={notebookTitle}>
              {notebookTitle || t.nav.defaultTitle}
            </span>
          </div>
        </div>
      </div>

      {/* Right: Workspace & Account Controls */}
      <div className="navbar-actions">
        {/* Toggle Sources Drawer Button */}
        {onToggleSources && (
          <button
            type="button"
            id="btn-toggle-sources"
            onClick={onToggleSources}
            className={`navbar-action-btn ${isSourcesOpen ? "active" : ""}`}
            title={t.nav.toggleFilings}
          >
            <FileTextIcon size={14} color="var(--accent-primary)" />
            <span className="navbar-btn-text">{t.nav.filings}: <strong>{sourcesCount}</strong></span>
            <span className={`navbar-source-indicator ${sourcesCount > 0 ? "ready" : ""}`} />
          </button>
        )}

        {/* Toggle PDF Split-View Button */}
        {onToggleSplitView && (
          <button
            type="button"
            id="btn-toggle-splitview"
            onClick={onToggleSplitView}
            className={`navbar-action-btn split-toggle ${isSplitViewOpen ? "active" : ""}`}
            title={isSplitViewOpen ? t.nav.closeReader : t.nav.openReader}
            aria-label={t.nav.toggleReader}
          >
            <TableIcon size={14} />
            <span className="navbar-btn-text">{t.nav.splitView} [{isSplitViewOpen ? t.nav.splitViewOn : t.nav.splitViewOff}]</span>
          </button>
        )}

        {/* Language Switcher */}
        <LanguageToggle size="sm" />

        <div className="navbar-divider" />

        {/* User / Auth Indicator */}
        {user ? (
          <div
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="navbar-user-chip"
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
          <div className="navbar-guest-actions">
            <span className="navbar-guest-badge">
              {t.nav.guestMode}
            </span>
            <button onClick={onOpenAuthModal} className="navbar-login-btn">
              <UserIcon size={12} />
              <span>{t.common.signIn}</span>
            </button>
          </div>
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
