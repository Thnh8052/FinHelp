import React, { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LogOutIcon, ShieldIcon, UserIcon } from "../common/Icons";
import "./auth.css";

interface UserDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenAuthModal: () => void;
}

export const UserDropdown: React.FC<UserDropdownProps> = ({
  isOpen,
  onClose,
  onOpenAuthModal,
}) => {
  const { user, isGuest, guestQuota, logout } = useAuth();
  const { t } = useLanguage();
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div ref={dropdownRef} className="dropdown-menu">
      {/* Header Info */}
      <div className="dropdown-header">
        {user ? (
          <div>
            <div className="dropdown-title-row">
              <span className="dropdown-name">
                {user.full_name || user.username}
              </span>
              <span className={`dropdown-role-tag ${user.role === "admin" ? "admin" : "user"}`}>
                {user.role === "admin" ? t.nav.roleAdmin : t.userDropdown.roleMember}
              </span>
            </div>
            <div className="dropdown-email">
              {user.email}
            </div>
            <div className="dropdown-handle">
              @{user.username}
            </div>
          </div>
        ) : (
          <div>
            <div className="dropdown-title-row">
              <span className="dropdown-name">
                {t.userDropdown.guestUser}
              </span>
              <span className="dropdown-role-tag guest">
                {t.userDropdown.notSignedIn}
              </span>
            </div>
            <div className="dropdown-email">
              {t.userDropdown.trialSession}
            </div>
          </div>
        )}
      </div>

      {/* Quota Status */}
      <div className="dropdown-section">
        <div className="dropdown-section-title">
          {t.userDropdown.usageQuota}
        </div>

        {user ? (
          <div className="dropdown-quota-list">
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">{t.userDropdown.uploadedFilings}</span>
              <span className="dropdown-metric-val">
                {t.userDropdown.maxDocs.replace("{n}", String(user.quota.max_upload_documents))}
              </span>
            </div>
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">{t.userDropdown.queriesToday}</span>
              <span className="dropdown-metric-val">
                {user.quota.messages_used_today} / {user.quota.daily_messages_limit}
              </span>
            </div>
          </div>
        ) : (
          <div className="dropdown-quota-list">
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">{t.userDropdown.uploadedFilings}</span>
              <span className="dropdown-metric-val">
                {t.userDropdown.maxDocs.replace("{n}", String(guestQuota?.max_upload_documents || 1))}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Action Links */}
      <div className="dropdown-actions">
        {user?.role === "admin" && (
          <button
            onClick={() => {
              onClose();
              navigate("/admin");
            }}
            className="dropdown-action-item"
          >
            <ShieldIcon size={14} color="#3b82f6" />
            <span>{t.userDropdown.adminDashboard}</span>
          </button>
        )}

        {isGuest ? (
          <button
            onClick={() => {
              onClose();
              onOpenAuthModal();
            }}
            className="dropdown-action-login"
          >
            <UserIcon size={14} />
            <span>{t.userDropdown.signInToSave}</span>
          </button>
        ) : (
          <button
            onClick={() => {
              onClose();
              logout();
            }}
            className="dropdown-action-logout"
          >
            <LogOutIcon size={14} />
            <span>{t.userDropdown.signOut}</span>
          </button>
        )}
      </div>
    </div>
  );
};
