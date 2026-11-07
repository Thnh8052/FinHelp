import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { UserDropdown } from "../auth/UserDropdown";
import { FileTextIcon, MenuIcon, TableIcon, UserIcon } from "../common/Icons";
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
      {/* Left: App Logo & Workspace Title (Mockup V3) */}
      <div className="navbar-brand">
        {onToggleSidebar && (
          <button
            type="button"
            id="btn-toggle-sidebar"
            onClick={onToggleSidebar}
            className={`navbar-sidebar-btn ${isSidebarOpen ? "active" : ""}`}
            title="Thu gọn / Mở sidebar (Ctrl+B)"
            aria-label="Thu gọn hoặc mở sidebar"
          >
            <MenuIcon size={16} />
          </button>
        )}
        <div className="navbar-brand-logo">
          <span>F</span>
        </div>
        <div className="navbar-brand-info">
          <div className="navbar-brand-row">
            <span className="navbar-brand-title">FinHelp</span>
            <span className="navbar-version-badge">V3</span>
          </div>
          <div className="navbar-brand-subtitle">
            <span className="navbar-status-dot" />
            <span className="navbar-notebook-title" title={notebookTitle}>
              {notebookTitle || "Phân Tích Báo Cáo Tài Chính"}
            </span>
          </div>
        </div>
      </div>

      {/* Right: Workspace & Account Controls */}
      <div className="navbar-actions">
        {/* Toggle Sources Drawer Button (Bật / Tắt danh sách nguồn phiên này) */}
        {onToggleSources && (
          <button
            type="button"
            id="btn-toggle-sources"
            onClick={onToggleSources}
            className={`navbar-action-btn ${isSourcesOpen ? "active" : ""}`}
            title="Mở hoặc thu gọn danh sách BCTC của phiên chat này"
          >
            <FileTextIcon size={14} color="var(--accent-primary)" />
            <span>Nguồn phiên này: <strong>{sourcesCount} BCTC</strong></span>
            <span className={`navbar-source-indicator ${sourcesCount > 0 ? "ready" : ""}`} />
          </button>
        )}

        {/* Toggle PDF Split-View Button (Bật / Tắt trình đọc BCTC gốc) */}
        {onToggleSplitView && (
          <button
            type="button"
            id="btn-toggle-splitview"
            onClick={onToggleSplitView}
            className={`navbar-action-btn split-toggle ${isSplitViewOpen ? "active" : ""}`}
            title="Mở song song hoặc thu gọn trình đọc BCTC đối chiếu"
          >
            <TableIcon size={14} />
            <span>Trình đọc BCTC [{isSplitViewOpen ? "On" : "Off"}]</span>
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
              Chế độ dùng thử
            </span>
            <button onClick={onOpenAuthModal} className="navbar-login-btn">
              <UserIcon size={12} />
              <span>Đăng nhập</span>
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
