import React, { useEffect } from "react";
import { AlertCircleIcon, CheckIcon, CloseIcon, InfoCircleIcon } from "./Icons";
import "./toast.css";

export interface ToastData {
  id: string;
  message: string;
  type?: "info" | "warning" | "error" | "success";
  actionLabel?: string;
  onAction?: () => void;
  durationMs?: number;
}

interface ToastProps {
  toast: ToastData | null;
  onClose: () => void;
}

/**
 * Top-Center Toast Notification Component
 * Hiển thị thông báo dạng thanh nhỏ phía trên trung tâm màn hình,
 * tự biến mất sau vài giây hoặc cho phép bấm nút tương tác nhanh (như Đăng nhập ngay)
 * mà không chặn người dùng bằng pop-up confirm gây khó chịu.
 */
export const Toast: React.FC<ToastProps> = ({ toast, onClose }) => {
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      onClose();
    }, toast.durationMs || 5000);
    return () => clearTimeout(timer);
  }, [toast, onClose]);

  if (!toast) return null;

  const type = toast.type || "info";

  const getIcon = () => {
    switch (type) {
      case "warning":
      case "error":
        return <AlertCircleIcon size={16} color="#f87171" />;
      case "success":
        return <CheckIcon size={16} color="#34d399" />;
      default:
        return <InfoCircleIcon size={16} color="#60a5fa" />;
    }
  };

  return (
    <div className={`toast-container toast-${type}`}>
      <div className="toast-icon">
        {getIcon()}
      </div>

      <div className="toast-message">
        {toast.message}
      </div>

      {toast.actionLabel && toast.onAction && (
        <button
          onClick={() => {
            toast.onAction?.();
            onClose();
          }}
          className="toast-action-btn"
        >
          {toast.actionLabel}
        </button>
      )}

      <button
        onClick={onClose}
        aria-label="Đóng thông báo"
        className="toast-close-btn"
      >
        <CloseIcon size={14} />
      </button>
    </div>
  );
};
