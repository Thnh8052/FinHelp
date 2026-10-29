import React, { useEffect, useRef } from "react";
import { useAuth } from "../../context/AuthContext";
import { LogOutIcon, ShieldIcon, UserIcon } from "../common/Icons";
import "./auth.css";

interface UserDropdownProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenAuthModal: () => void;
  onOpenAdminDashboard: () => void;
}

export const UserDropdown: React.FC<UserDropdownProps> = ({
  isOpen,
  onClose,
  onOpenAuthModal,
  onOpenAdminDashboard,
}) => {
  const { user, isGuest, guestQuota, logout } = useAuth();
  const dropdownRef = useRef<HTMLDivElement>(null);

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
                {user.role === "admin" ? "ADMIN" : "THÀNH VIÊN"}
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
                Khách Vãng Lai
              </span>
              <span className="dropdown-role-tag guest">
                CHƯA ĐĂNG NHẬP
              </span>
            </div>
            <div className="dropdown-email">
              Chế độ trải nghiệm
            </div>
          </div>
        )}
      </div>

      {/* Quota Status */}
      <div className="dropdown-section">
        <div className="dropdown-section-title">
          Hạn Mức Sử Dụng
        </div>

        {user ? (
          <div className="dropdown-quota-list">
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">Tài liệu tải lên:</span>
              <span className="dropdown-metric-val">
                Tối đa {user.quota.max_upload_documents} tài liệu / notebook
              </span>
            </div>
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">Lượt hỏi hôm nay:</span>
              <span className="dropdown-metric-val">
                {user.quota.messages_used_today} / {user.quota.daily_messages_limit}
              </span>
            </div>
          </div>
        ) : (
          <div className="dropdown-quota-list">
            <div className="dropdown-metric-row">
              <span className="dropdown-metric-label">Tài liệu tải lên:</span>
              <span className="dropdown-metric-val">
                Tối đa {guestQuota?.max_upload_documents || 1} tài liệu
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
              onOpenAdminDashboard();
            }}
            className="dropdown-action-item"
          >
            <ShieldIcon size={14} color="#3b82f6" />
            <span>Admin Dashboard (Hiệu năng & Chi phí)</span>
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
            <span>Đăng Nhập / Đăng Ký Tài Khoản</span>
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
            <span>Đăng Xuất</span>
          </button>
        )}
      </div>
    </div>
  );
};
