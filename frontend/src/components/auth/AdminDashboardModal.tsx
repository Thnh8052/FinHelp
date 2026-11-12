import React, { useEffect, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { authService } from "../../services/auth";
import { errorText } from "../../services/api";
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
  const { t } = useLanguage();

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await authService.getAdminDashboard();
      setStats(data);
    } catch (err: unknown) {
      setError(errorText(err, t, t.admin.loadFailed));
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
                {t.admin.title}
              </h2>
              <p className="auth-subtitle">
                {t.admin.subtitle}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="auth-close-btn">
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="auth-body">
          {loading && <p className="admin-loading-text">{t.admin.loading}</p>}
          {error && <div className="auth-alert-error no-top-margin">{error}</div>}

          {stats && (
            <div>
              {/* Metrics Grid */}
              <div className="admin-grid">
                {/* Card 1: Users */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">{t.admin.userAccounts}</span>
                  <div className="admin-metric-val">
                    {stats.total_users}
                  </div>
                  <div className="admin-metric-sub">
                    {t.admin.activeAccounts.replace("{n}", String(stats.active_users))}
                  </div>
                </div>

                {/* Card 2: Tokens */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">{t.admin.consumedTokens}</span>
                  <div className="admin-metric-val tokens">
                    {stats.api_metrics.total_tokens_consumed.toLocaleString()}
                  </div>
                  <div className="admin-metric-sub">
                    {t.admin.clusterSub}
                  </div>
                </div>
              </div>

              {/* Performance Section */}
              <div className="admin-perf-bar">
                <div>
                  <div className="admin-perf-status">
                    {t.admin.databaseCluster.replace("{status}", stats.system_performance.database)}
                  </div>
                  <div className="admin-perf-latency">
                    {t.admin.averageLatency.replace("{ms}", String(stats.system_performance.latency_ms ?? "—"))}
                  </div>
                </div>
                <span className="admin-badge-active">
                  {t.admin.active}
                </span>
              </div>

              {/* Policy Section */}
              <div className="admin-policy-box">
                <h4 className="admin-policy-title">
                  {t.admin.policyTitle}
                </h4>
                <div className="admin-policy-text">
                  <div>• <strong>{t.admin.guestLabel}</strong> {t.admin.guestPolicy}</div>
                  <div>• <strong>{t.admin.memberLabel}</strong> {t.admin.memberPolicy}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
