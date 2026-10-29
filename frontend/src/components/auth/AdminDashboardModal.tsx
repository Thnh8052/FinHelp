import React, { useEffect, useState } from "react";
import { authService } from "../../services/auth";
import { AdminDashboardStats } from "../../types/auth";
import { CloseIcon, ShieldIcon } from "../common/Icons";
import "./auth.css";

interface AdminDashboardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminDashboardModal: React.FC<AdminDashboardModalProps> = ({ isOpen, onClose }) => {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.getAdminDashboard();
      setStats(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không thể tải số liệu Admin Dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStats();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop admin" onClick={onClose}>
      <div className="admin-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="auth-header">
          <div className="auth-header-left">
            <ShieldIcon size={18} color="#3b82f6" />
            <div>
              <h2 className="auth-title">
                Hệ Thống Quản Trị & Giám Sát Chi Phí API (Admin)
              </h2>
              <p className="auth-subtitle">
                Dành riêng cho Quản trị viên hệ thống (Vũ Thành)
              </p>
            </div>
          </div>
          <button onClick={onClose} className="auth-close-btn">
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="auth-body">
          {loading && <p className="admin-loading-text">Đang tải số liệu hệ thống...</p>}
          {error && <div className="auth-alert-error no-top-margin">{error}</div>}

          {stats && (
            <div>
              {/* Metrics Grid */}
              <div className="admin-grid">
                {/* Card 1: Users */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">Tài khoản người dùng</span>
                  <div className="admin-metric-val">
                    {stats.total_users}
                  </div>
                  <div className="admin-metric-sub">
                    {stats.active_users} tài khoản đang kích hoạt
                  </div>
                </div>

                {/* Card 2: Tokens */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">Tổng Tokens Tiêu Thụ</span>
                  <div className="admin-metric-val tokens">
                    {stats.api_metrics.total_tokens_consumed.toLocaleString()}
                  </div>
                  <div className="admin-metric-sub">
                    Cụm AI Phân Tích Tài Chính
                  </div>
                </div>

                {/* Card 3: Estimated Cost */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">Ước tính Chi Phí API</span>
                  <div className="admin-metric-val cost">
                    ${stats.api_metrics.total_estimated_cost_usd.toFixed(4)}
                  </div>
                  <div className="admin-metric-sub">
                    ~{(stats.api_metrics.total_estimated_cost_usd * 25400).toLocaleString("vi-VN")} VND
                  </div>
                </div>
              </div>

              {/* Performance Section */}
              <div className="admin-perf-bar">
                <div>
                  <div className="admin-perf-status">
                    Trạng Thái Cơ Sở Dữ Liệu: {stats.system_performance.database}
                  </div>
                  <div className="admin-perf-latency">
                    Độ trễ trung bình: {stats.system_performance.latency_ms} ms
                  </div>
                </div>
                <span className="admin-badge-active">
                  ACTIVE
                </span>
              </div>

              {/* Policy Section */}
              <div className="admin-policy-box">
                <h4 className="admin-policy-title">
                  Chính Sách Giới Hạn Tài Nguyên (Access Control Policy)
                </h4>
                <div className="admin-policy-text">
                  <div>• <strong>Chưa đăng nhập (Khách dùng thử):</strong> Giới hạn tối đa <strong>1 tài liệu</strong>, không giới hạn số câu hỏi.</div>
                  <div>• <strong>Đã đăng nhập (Thành viên):</strong> Mở khóa tối đa <strong>5 tài liệu / 1 Notebook</strong> phân tích tài chính chuyên sâu.</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
