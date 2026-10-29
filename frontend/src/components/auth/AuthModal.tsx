import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { authService } from "../../services/auth";
import { CloseIcon, SparklesIcon } from "../common/Icons";
import "./auth.css";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "signin" | "signup";
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, initialTab = "signin" }) => {
  const { login, register, continueAsGuest } = useAuth();
  const [tab, setTab] = useState<"signin" | "signup" | "forgot">(initialTab);

  // Form states
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");

  // Forgot password states
  const [forgotStep, setForgotStep] = useState<1 | 2>(1);
  const [forgotEmail, setForgotEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [otpDebug, setOtpDebug] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(identifier, password);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại. Vui lòng kiểm tra lại tài khoản.");
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, username, password, fullName);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại. Email hoặc username có thể đã tồn tại.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authService.forgotPassword(forgotEmail);
      if (res.otp_debug) {
        setOtpDebug(res.otp_debug);
      }
      setSuccessMsg("Mã OTP đã được tạo. Vui lòng nhập mã và mật khẩu mới bên dưới.");
      setForgotStep(2);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không thể gửi mã OTP.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgotStep2 = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authService.resetPassword(forgotEmail, otpCode, newPassword);
      setSuccessMsg(res.message);
      setTimeout(() => {
        setTab("signin");
        setForgotStep(1);
        setSuccessMsg(null);
        setOtpDebug(null);
      }, 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Xác thực OTP thất bại.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="auth-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="auth-header">
          <div>
            <h2 className="auth-title">
              {tab === "signin" && "Đăng Nhập Hệ Thống"}
              {tab === "signup" && "Tạo Tài Khoản Mới"}
              {tab === "forgot" && "Khôi Phục Mật Khẩu"}
            </h2>
            <p className="auth-subtitle">
              Nền tảng AI phân tích Báo cáo tài chính chuẩn doanh nghiệp
            </p>
          </div>
          <button onClick={onClose} className="auth-close-btn">
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Alerts */}
        {error && <div className="auth-alert-error">{error}</div>}
        {successMsg && <div className="auth-alert-success">{successMsg}</div>}

        <div className="auth-body">
          {/* TAB 1: SIGN IN */}
          {tab === "signin" && (
            <div>
              <form onSubmit={handleSignIn} className="auth-form">
                <div className="auth-field">
                  <label className="auth-label">Email hoặc Tên đăng nhập</label>
                  <input
                    type="text"
                    required
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="admin hoặc admin@finanalyst.ai"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <div className="auth-label-row">
                    <label className="auth-label">Mật khẩu</label>
                    <button
                      type="button"
                      onClick={() => setTab("forgot")}
                      className="auth-forgot-link"
                    >
                      Quên mật khẩu?
                    </button>
                  </div>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="auth-submit-btn"
                >
                  {loading ? "Đang xác thực..." : "Đăng Nhập"}
                </button>
              </form>

              <div className="auth-guest-section">
                {/* Guest Preview */}
                <div className="auth-guest-box">
                  <button
                    type="button"
                    onClick={() => {
                      continueAsGuest();
                      onClose();
                    }}
                    className="auth-guest-link"
                  >
                    <SparklesIcon size={12} />
                    <span>Tiếp tục trải nghiệm ở Chế độ dùng thử</span>
                  </button>
                </div>
              </div>

              {/* Bottom Switch */}
              <div className="auth-footer-switch">
                Chưa có tài khoản?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signup");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  Đăng ký ngay
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: SIGN UP */}
          {tab === "signup" && (
            <div>
              <form onSubmit={handleSignUp} className="auth-form-dense">
                <div className="auth-field">
                  <label className="auth-label">
                    Email <span className="auth-required">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="tenban@congty.com"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Tên đăng nhập <span className="auth-required">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="vd: analyst_hanoi"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Mật khẩu <span className="auth-required">*</span> (Tối thiểu 6 ký tự)
                  </label>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="auth-input"
                  />
                </div>

                <div className="auth-field">
                  <label className="auth-label">
                    Họ và tên (Tùy chọn)
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="vd: Vũ Thành"
                    className="auth-input"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="auth-submit-btn spaced"
                >
                  {loading ? "Đang tạo tài khoản..." : "Hoàn Tất Đăng Ký"}
                </button>
              </form>

              <div className="auth-footer-switch">
                Đã có tài khoản?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setTab("signin");
                    setError(null);
                  }}
                  className="auth-link-btn"
                >
                  Đăng nhập
                </button>
              </div>
            </div>
          )}

          {/* TAB 3: FORGOT PASSWORD */}
          {tab === "forgot" && (
            <div>
              {forgotStep === 1 ? (
                <form onSubmit={handleForgotStep1} className="auth-form">
                  <p className="auth-hint-text">
                    Nhập địa chỉ email đăng ký để nhận mã xác thực OTP 6 số (thời hạn 15 phút):
                  </p>
                  <div>
                    <input
                      type="email"
                      required
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      placeholder="email@example.com"
                      className="auth-input"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="auth-submit-btn"
                  >
                    {loading ? "Đang xử lý..." : "Gửi Mã OTP"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleForgotStep2} className="auth-form">
                  {otpDebug && (
                    <div className="auth-otp-debug">
                      Mã OTP thử nghiệm (Đồ án): <strong>{otpDebug}</strong>
                    </div>
                  )}

                  <div className="auth-field">
                    <label className="auth-label">
                      Mã OTP (6 chữ số)
                    </label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={otpCode}
                      onChange={(e) => setOtpCode(e.target.value)}
                      placeholder="123456"
                      className="auth-input"
                    />
                  </div>

                  <div className="auth-field">
                    <label className="auth-label">
                      Mật khẩu mới (Tối thiểu 6 ký tự)
                    </label>
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      className="auth-input"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="auth-submit-btn"
                  >
                    {loading ? "Đang xác thực..." : "Xác Nhận & Đặt Lại Mật Khẩu"}
                  </button>
                </form>
              )}

              <div className="auth-footer-switch">
                <button
                  type="button"
                  onClick={() => {
                    setTab("signin");
                    setError(null);
                    setSuccessMsg(null);
                  }}
                  className="auth-link-btn secondary"
                >
                  Quay lại Đăng nhập
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
