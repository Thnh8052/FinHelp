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
      setError(err instanceof Error ? err.message : "Unable to load Admin Dashboard metrics");
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
                System Administration &amp; Cost Monitoring (Admin)
              </h2>
              <p className="auth-subtitle">
                System Administrator Console
              </p>
            </div>
          </div>
          <button onClick={onClose} className="auth-close-btn">
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="auth-body">
          {loading && <p className="admin-loading-text">Loading system metrics...</p>}
          {error && <div className="auth-alert-error no-top-margin">{error}</div>}

          {stats && (
            <div>
              {/* Metrics Grid */}
              <div className="admin-grid">
                {/* Card 1: Users */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">User Accounts</span>
                  <div className="admin-metric-val">
                    {stats.total_users}
                  </div>
                  <div className="admin-metric-sub">
                    {stats.active_users} active accounts
                  </div>
                </div>

                {/* Card 2: Tokens */}
                <div className="admin-metric-card">
                  <span className="admin-metric-label">Total Consumed Tokens</span>
                  <div className="admin-metric-val tokens">
                    {stats.api_metrics.total_tokens_consumed.toLocaleString()}
                  </div>
                  <div className="admin-metric-sub">
                    Financial Intelligence Cluster
                  </div>
                </div>
              </div>

              {/* Performance Section */}
              <div className="admin-perf-bar">
                <div>
                  <div className="admin-perf-status">
                    Database Cluster: {stats.system_performance.database}
                  </div>
                  <div className="admin-perf-latency">
                    Average Latency: {stats.system_performance.latency_ms} ms
                  </div>
                </div>
                <span className="admin-badge-active">
                  ACTIVE
                </span>
              </div>

              {/* Policy Section */}
              <div className="admin-policy-box">
                <h4 className="admin-policy-title">
                  Access Control &amp; Resource Policy
                </h4>
                <div className="admin-policy-text">
                  <div>• <strong>Guest Trial:</strong> Maximum <strong>1 filing</strong> per session, interactive questions enabled.</div>
                  <div>• <strong>Member Account:</strong> Unlocks up to <strong>5 filings</strong> per notebook for cross-filing analysis.</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
