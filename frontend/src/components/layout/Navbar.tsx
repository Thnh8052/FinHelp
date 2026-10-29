import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { UserDropdown } from "../auth/UserDropdown";
import { DownloadIcon, UserIcon } from "../common/Icons";
import "./layout.css";

interface NavbarProps {
  notebookTitle: string;
  onExportReport?: () => void;
  onOpenAuthModal: () => void;
  onOpenAdminDashboard: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  notebookTitle: _notebookTitle,
  onExportReport,
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
      {/* Left: App Logo */}
      <div className="navbar-brand">
        <span className="navbar-brand-title">
          FinAnalyst
        </span>
        <div className="navbar-brand-subtitle">
          <span className="navbar-status-dot" />
          <span>Hệ thống Phân tích BCTC (SEC Form 10-K)</span>
        </div>
      </div>

      {/* Right: Clean Actions */}
      <div className="navbar-actions">
        {onExportReport && (
          <button onClick={onExportReport} className="navbar-export-btn">
            <DownloadIcon size={13} />
            <span>Xuất báo cáo</span>
          </button>
        )}

        {/* User / Auth Indicator */}
        {user ? (
          <div
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="navbar-user-chip"
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
