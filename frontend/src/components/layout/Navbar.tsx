import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
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
  onExportReport?: () => void;
  onOpenAuthModal: () => void;
  onOpenAdminDashboard: () => void;
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
  onExportReport: _onExportReport,
  onOpenAuthModal,
  onOpenAdminDashboard,
  onNavigateHome,
}) => {
  const { user } = useAuth();
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
            title="Toggle sidebar (Ctrl+B)"
            aria-label="Toggle sidebar"
          >
            <MenuIcon size={16} />
          </button>
        )}
        <div className="cursor-pointer" onClick={onNavigateHome} title="Return to FinHelp Home">
          <FinHelpLogo size="sm" showText={false} />
        </div>
        <div className="navbar-brand-info">
          <div className="navbar-brand-row">
            <span
              className="navbar-brand-title cursor-pointer hover:text-blue-400 transition-colors"
              onClick={onNavigateHome}
              title="Return to FinHelp Home"
            >
              FinHelp
            </span>
            <span className="navbar-version-badge">V3</span>
          </div>
          <div className="navbar-brand-subtitle">
            <span className="navbar-status-dot" />
            <span className="navbar-notebook-title" title={notebookTitle}>
              {notebookTitle || "Financial Statement Analysis"}
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
            title="Toggle filing sources for this session"
          >
            <FileTextIcon size={14} color="var(--accent-primary)" />
            <span className="navbar-btn-text">Filings: <strong>{sourcesCount}</strong></span>
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
            title="Toggle split-view document reader"
          >
            <TableIcon size={14} />
            <span className="navbar-btn-text">Split-View [{isSplitViewOpen ? "On" : "Off"}]</span>
          </button>
        )}

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
              {isAdmin ? "ADMIN" : "USER"}
            </span>
          </div>
        ) : (
          <div className="navbar-guest-actions">
            <span className="navbar-guest-badge">
              Guest Mode
            </span>
            <button onClick={onOpenAuthModal} className="navbar-login-btn">
              <UserIcon size={12} />
              <span>Sign In</span>
            </button>
          </div>
        )}

        {/* Dropdown Popover */}
        <UserDropdown
          isOpen={dropdownOpen}
          onClose={() => setDropdownOpen(false)}
          onOpenAuthModal={onOpenAuthModal}
          onOpenAdminDashboard={onOpenAdminDashboard}
        />
      </div>
    </header>
  );
};
