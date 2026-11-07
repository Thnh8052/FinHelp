import React, { useState, useEffect } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import { ApiInspectorModal, API_ENDPOINTS_CATALOG, ApiEndpointInfo } from "./ApiInspectorModal";
import "./LandingPage.css";

interface LandingPageProps {
  onEnterApp: () => void;
  onOpenAuth: (mode: "login" | "register") => void;
  isAuthenticated?: boolean;
}

export const LandingPage: React.FC<LandingPageProps> = ({
  onEnterApp,
  onOpenAuth,
  isAuthenticated = false,
}) => {
  const [apiModalOpen, setApiModalOpen] = useState(false);
  const [activeApiEndpoint, setActiveApiEndpoint] = useState<ApiEndpointInfo | null>(null);

  // Demo Query Selector in Product Preview
  const [activeQueryIndex, setActiveQueryIndex] = useState<number>(1);
  const [activeCitationAlert, setActiveCitationAlert] = useState<string | null>(null);

  // Live Backend Status Check
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [backendLatency, setBackendLatency] = useState<number | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      const start = performance.now();
      try {
        const res = await fetch("/health", { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const elapsed = Math.round(performance.now() - start);
          if (isMounted) {
            setBackendStatus("online");
            setBackendLatency(elapsed);
          }
          return;
        }
      } catch {
        // Fallback or offline
      }
      if (isMounted) {
        setBackendStatus("offline");
      }
    };
    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  const openApiDetails = (path: string, method: "POST" | "GET" | "PATCH" | "DELETE" = "POST") => {
    const ep = API_ENDPOINTS_CATALOG.find((item) => item.path === path && item.method === method);
    if (ep) {
      setActiveApiEndpoint(ep);
    } else {
      setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
    }
    setApiModalOpen(true);
  };

  return (
    <div className="fh-landing-root">
      {/* Background radial glow */}
      <div className="fh-hero-glow" />

      {/* ========================================================================= */}
      {/* 1. NAVBAR                                                                 */}
      {/* ========================================================================= */}
      <header className="fh-navbar">
        <div className="fh-navbar-inner">
          {/* Logo with clean emblem */}
          <FinHelpLogo
            size="md"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="cursor-pointer"
          />

          {/* Navigation Links */}
          <nav className="fh-nav-links">
            <a href="#features" className="fh-nav-link">
              Features
            </a>
            <a href="#how-it-works" className="fh-nav-link">
              How it works
            </a>
            <a href="#use-cases" className="fh-nav-link">
              Use Cases
            </a>
            <a href="#trust" className="fh-nav-link">
              Trust
            </a>
          </nav>

          {/* Right Actions: API Map, Backend Status & Auth CTA */}
          <div className="fh-navbar-actions">
            {/* Backend Connectivity Indicator */}
            <div
              onClick={() => openApiDetails("/health", "GET")}
              className="fh-btn-api-map cursor-pointer"
              title="Trạng thái kết nối máy chủ backend FastAPI (127.0.0.1:8000)"
            >
              <span
                style={{
                  width: "7px",
                  height: "7px",
                  borderRadius: "50%",
                  backgroundColor: backendStatus === "online" ? "#10b981" : "#f59e0b",
                  display: "inline-block",
                }}
              />
              <span>
                {backendStatus === "online" ? `API Online (${backendLatency}ms)` : "Sơ đồ 29 API"}
              </span>
            </div>

            {isAuthenticated ? (
              <button onClick={onEnterApp} className="fh-btn-primary">
                <span>Vào Không Gian Phân Tích</span>
                <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            ) : (
              <>
                <button onClick={() => onOpenAuth("login")} className="fh-btn-text">
                  Sign in
                </button>
                <button onClick={onEnterApp} className="fh-btn-primary">
                  Get Started
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* 2. HERO SECTION & PRODUCT PREVIEW                                         */}
      {/* ========================================================================= */}
      <section className="fh-hero fh-grid-pattern">
        <div className="fh-container">
          {/* Tagline */}
          <div className="fh-hero-badge">
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#3b82f6",
                display: "inline-block",
              }}
            />
            <span>AI-powered Financial Analysis</span>
          </div>

          {/* Title */}
          <h1 className="fh-hero-title">
            Understand Financial Reports.
            <br />
            <span className="fh-hero-gradient-text">Make Better Decisions.</span>
          </h1>

          {/* Subtitle */}
          <p className="fh-hero-subtitle">
            Upload financial reports, ask questions in natural language, and get answers grounded in your documents.
          </p>

          {/* Hero CTAs */}
          <div className="fh-hero-actions">
            <button onClick={onEnterApp} className="fh-btn-primary" style={{ padding: "12px 28px", fontSize: "15px" }}>
              <span>Get Started</span>
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </button>
            <a href="#features" className="fh-btn-secondary" style={{ padding: "12px 24px", fontSize: "15px" }}>
              Explore Features
            </a>
          </div>

          {/* Sample Question Chips */}
          <div className="fh-chips-container">
            <span style={{ fontSize: "12px", color: "#64748b", fontWeight: 600, marginRight: "4px" }}>
              Thử câu hỏi mẫu:
            </span>
            <button
              onClick={() => setActiveQueryIndex(1)}
              className={`fh-chip ${activeQueryIndex === 1 ? "active" : ""}`}
            >
              📈 So sánh doanh thu YoY
            </button>
            <button
              onClick={() => setActiveQueryIndex(2)}
              className={`fh-chip ${activeQueryIndex === 2 ? "active" : ""}`}
            >
              💰 Tính Free Cash Flow
            </button>
            <button
              onClick={() => setActiveQueryIndex(3)}
              className={`fh-chip ${activeQueryIndex === 3 ? "active" : ""}`}
            >
              🔍 Thuyết minh Dự phòng nợ
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* PRODUCT PREVIEW SHOWCASE                                                  */}
        {/* ========================================================================= */}
        <div className="fh-preview-card">
          {/* Topbar */}
          <div className="fh-preview-topbar">
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div className="fh-window-dots">
                <span className="fh-dot" style={{ backgroundColor: "#ef4444" }} />
                <span className="fh-dot" style={{ backgroundColor: "#f59e0b" }} />
                <span className="fh-dot" style={{ backgroundColor: "#10b981" }} />
              </div>
              <span style={{ color: "#94a3b8", fontWeight: 600 }}>FinHelp Workspace · Session #104</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <button
                onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                className="fh-api-pill fh-api-pill-post"
                title="Bấm để xem đặc tả API gửi câu hỏi"
              >
                <span>POST /api/v1/chat/query</span>
              </button>
              <span
                style={{
                  padding: "3px 10px",
                  borderRadius: "6px",
                  backgroundColor: "#172554",
                  border: "1px solid #1e40af",
                  color: "#93c5fd",
                  fontSize: "11px",
                  fontWeight: 600,
                }}
              >
                2 reports selected
              </span>
            </div>
          </div>

          {/* Q&A Body */}
          <div className="fh-preview-body">
            {/* User Bubble */}
            <div className="fh-user-bubble-wrapper">
              <div className="fh-user-bubble">
                {activeQueryIndex === 1 &&
                  "Compare the revenue growth of these two companies and show the main financial drivers."}
                {activeQueryIndex === 2 &&
                  "Calculate Free Cash Flow (FCF = Cash from Operations - CapEx) for the latest fiscal year."}
                {activeQueryIndex === 3 &&
                  "Check the footnote disclosure on allowances for doubtful accounts and trade receivables."}
              </div>
            </div>

            {/* AI Grounded Answer Card */}
            <div className="fh-ai-response-card">
              <div className="fh-ai-header">
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ color: "#cbd5e1", fontWeight: 600 }}>AI-generated answer</span>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    style={{
                      fontSize: "11px",
                      color: "#60a5fa",
                      fontFamily: "monospace",
                      cursor: "pointer",
                      background: "none",
                      border: "none",
                      textDecoration: "underline",
                    }}
                  >
                    (Xử lý bởi /chat/query)
                  </button>
                </div>
                <span
                  style={{
                    color: "#34d399",
                    backgroundColor: "rgba(16, 185, 129, 0.12)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    padding: "3px 10px",
                    borderRadius: "9999px",
                    fontSize: "11px",
                    fontWeight: 600,
                  }}
                >
                  ✓ Grounded in uploaded reports
                </span>
              </div>

              {/* Dynamic Answer content */}
              {activeQueryIndex === 1 && (
                <>
                  <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Company A reported higher revenue growth</strong> over the
                    fiscal period. The answer is supported by the relevant figures and references in the uploaded
                    reports:
                  </p>
                  <div className="fh-table-wrapper">
                    <table className="fh-table">
                      <thead>
                        <tr>
                          <th>Company</th>
                          <th style={{ textAlign: "right" }}>FY22 Revenue</th>
                          <th style={{ textAlign: "right" }}>FY23 Revenue</th>
                          <th style={{ textAlign: "right" }}>YoY Growth</th>
                          <th style={{ textAlign: "center" }}>Reference</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td style={{ fontWeight: 600, color: "#f8fafc", fontFamily: "sans-serif" }}>Company A</td>
                          <td style={{ textAlign: "right", color: "#94a3b8" }}>$14,200M</td>
                          <td style={{ textAlign: "right", color: "#34d399", fontWeight: 700 }}>$17,902M</td>
                          <td style={{ textAlign: "right", color: "#34d399", fontWeight: 700 }}>+26.1%</td>
                          <td style={{ textAlign: "center" }}>
                            <button
                              onClick={() =>
                                setActiveCitationAlert(
                                  "Trích dẫn [1]: Company_A_Report.pdf — Trang 45 (Báo cáo Kết quả Kinh doanh). Endpoint xem file gốc: GET /api/v1/documents/{document_id}/file#page=45"
                                )
                              }
                              className="fh-citation-btn"
                            >
                              [1] Page 45
                            </button>
                          </td>
                        </tr>
                        <tr>
                          <td style={{ fontWeight: 600, color: "#f8fafc", fontFamily: "sans-serif" }}>Company B</td>
                          <td style={{ textAlign: "right", color: "#94a3b8" }}>$28,500M</td>
                          <td style={{ textAlign: "right", color: "#f1f5f9" }}>$30,120M</td>
                          <td style={{ textAlign: "right", color: "#f1f5f9" }}>+5.7%</td>
                          <td style={{ textAlign: "center" }}>
                            <button
                              onClick={() =>
                                setActiveCitationAlert(
                                  "Trích dẫn [2]: Company_B_Report.pdf — Trang 32 (Item 8 Financial Disclosures). Endpoint xem file gốc: GET /api/v1/documents/{document_id}/file#page=32"
                                )
                              }
                              className="fh-citation-btn"
                            >
                              [2] Page 32
                            </button>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </>
              )}

              {activeQueryIndex === 2 && (
                <>
                  <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Free Cash Flow (FCF)</strong> được tính toán trực tiếp từ Báo
                    cáo Lưu chuyển tiền tệ hợp nhất:
                  </p>
                  <div
                    style={{
                      background: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: "12px",
                      padding: "16px",
                      fontSize: "13px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>(+) Lưu chuyển tiền từ HĐ kinh doanh (CFO):</span>
                      <span style={{ color: "#34d399", fontWeight: 700 }}>$12,195M</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>(-) Chi mua sắm TSCĐ (CapEx):</span>
                      <span style={{ color: "#f87171", fontWeight: 700 }}>-$9,102M</span>
                    </div>
                    <div
                      style={{
                        paddingTop: "8px",
                        borderTop: "1px solid #334155",
                        display: "flex",
                        justifyContent: "space-between",
                        color: "#ffffff",
                        fontWeight: 700,
                        fontSize: "14px",
                      }}
                    >
                      <span>(=) Free Cash Flow (FCF):</span>
                      <span style={{ color: "#34d399" }}>+$3,093M</span>
                    </div>
                  </div>
                </>
              )}

              {activeQueryIndex === 3 && (
                <>
                  <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Thuyết minh Dự phòng nợ phải thu khó đòi:</strong> Hệ thống đã
                    bóc tách chi tiết dư nợ quá hạn và mức trích lập tương ứng:
                  </p>
                  <div
                    style={{
                      background: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: "12px",
                      padding: "16px",
                      fontSize: "13px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>• Nợ quá hạn 1–6 tháng:</span>
                      <span style={{ color: "#f8fafc" }}>$45.2M (Đã trích lập $12.0M)</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>• Nợ quá hạn trên 1 năm:</span>
                      <span style={{ color: "#fbbf24", fontWeight: 700 }}>$18.5M (Đã trích lập 100%)</span>
                    </div>
                  </div>
                </>
              )}

              {/* Citation Alert notification */}
              {activeCitationAlert && (
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: "10px",
                    backgroundColor: "rgba(30, 58, 138, 0.45)",
                    border: "1px solid rgba(59, 130, 246, 0.6)",
                    fontSize: "12.5px",
                    color: "#bfdbfe",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span>📄</span>
                    <span>{activeCitationAlert}</span>
                  </div>
                  <button
                    onClick={() => setActiveCitationAlert(null)}
                    style={{ color: "#94a3b8", cursor: "pointer", background: "none", border: "none", fontWeight: 700 }}
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* Source references footer */}
              <div className="fh-sources-box">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      color: "#64748b",
                    }}
                  >
                    Source references (Trích dẫn kiểm chứng)
                  </span>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/{document_id}/file", "GET")}
                    className="fh-api-pill fh-api-pill-get"
                  >
                    GET /api/v1/documents/&#123;id&#125;/file
                  </button>
                </div>

                <div className="fh-sources-grid">
                  <div className="fh-source-item">
                    <span>
                      <strong>[1]</strong> Company_A_Report.pdf — Page 45 (Income Statement)
                    </span>
                    <span style={{ color: "#60a5fa", fontFamily: "monospace", fontSize: "11px" }}>#page=45</span>
                  </div>
                  <div className="fh-source-item">
                    <span>
                      <strong>[2]</strong> Company_B_Report.pdf — Page 32 (Item 8 Financials)
                    </span>
                    <span style={{ color: "#60a5fa", fontFamily: "monospace", fontSize: "11px" }}>#page=32</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 3. 01 — THE PROBLEM                                                       */}
      {/* ========================================================================= */}
      <section className="fh-section fh-section-alt">
        <div className="fh-container">
          <span className="fh-section-tag">01 — The Problem</span>
          <h2 className="fh-section-title">Financial reports are complex and time-consuming to analyze.</h2>
          <div className="fh-grid-4">
            <div className="fh-card">
              <div className="fh-card-icon">🔍</div>
              <h3 className="fh-card-title">Manual searching</h3>
              <p className="fh-card-text">
                Finding specific figures across lengthy reports and disclosure footnotes.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon">🧮</div>
              <h3 className="fh-card-title">Manual calculations</h3>
              <p className="fh-card-text">
                Comparing financial metrics across multiple fiscal quarters and periods.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon">📑</div>
              <h3 className="fh-card-title">Multiple documents</h3>
              <p className="fh-card-text">
                Switching between separate annual filings to find relevant disclosures.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon">💡</div>
              <h3 className="fh-card-title">Difficult insights</h3>
              <p className="fh-card-text">
                Turning raw accounting statements into understandable, structured answers.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 4. 02 — CORE FEATURES                                                     */}
      {/* ========================================================================= */}
      <section id="features" className="fh-section">
        <div className="fh-container">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <span className="fh-section-tag">02 — Core Features</span>
              <h2 className="fh-section-title">Everything you need to explore financial reports.</h2>
            </div>
            <div style={{ fontSize: "13px", color: "#94a3b8" }}>
              Bấm vào thẻ API trên từng tính năng để xem chi tiết kết nối
            </div>
          </div>

          <div className="fh-grid-3">
            {/* Feature 1 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">Document Upload</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/upload/{notebook_id}", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    POST /documents/upload
                  </button>
                </div>
                <p className="fh-card-text">
                  Upload financial reports in PDF format with automatic table recognition and contextual metadata
                  tagging.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Hỗ trợ: PDF, Form 10-K, BCTC Kiểm toán
              </div>
            </div>

            {/* Feature 2 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">AI-powered Q&A</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    POST /chat/query
                  </button>
                </div>
                <p className="fh-card-text">
                  Ask questions using natural language. Query across complex accounting disclosures without manual page
                  searching.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Trực tiếp trên Workspace Chat
              </div>
            </div>

            {/* Feature 3 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">Multi-report Comparison</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    Multi-document scope
                  </button>
                </div>
                <p className="fh-card-text">
                  Compare companies, fiscal periods, and financial indicators across multiple filings simultaneously.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Đối chiếu chéo 2+ công ty
              </div>
            </div>

            {/* Feature 4 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">Evidence-based Answers</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/{document_id}/file", "GET")}
                    className="fh-api-pill fh-api-pill-get"
                  >
                    GET /documents/&#123;id&#125;/file
                  </button>
                </div>
                <p className="fh-card-text">
                  See the supporting passages and exact document references behind every statement with PDF Split-View
                  jumping.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Xác minh số liệu gốc 100%
              </div>
            </div>

            {/* Feature 5 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">Financial Analysis</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    Calculator & Re-check
                  </button>
                </div>
                <p className="fh-card-text">
                  Calculate and interpret margins, growth rates, ratios, and cash flows with automated mathematical
                  verification.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Công thức toán học minh bạch
              </div>
            </div>

            {/* Feature 6 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <h3 className="fh-card-title">Conversation History</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/sessions/notebook/{notebook_id}", "GET")}
                    className="fh-api-pill fh-api-pill-get"
                  >
                    GET /chat/sessions
                  </button>
                </div>
                <p className="fh-card-text">
                  Save, search, and continue previous analysis sessions anytime with isolated session history per
                  notebook.
                </p>
              </div>
              <div style={{ marginTop: "16px", paddingTop: "12px", borderTop: "1px solid #1e293b", fontSize: "12px", color: "#60a5fa" }}>
                Lưu trữ phiên an toàn
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 5. 03 — HOW IT WORKS                                                      */}
      {/* ========================================================================= */}
      <section id="how-it-works" className="fh-section fh-section-alt">
        <div className="fh-container">
          <span className="fh-section-tag">03 — How It Works</span>
          <h2 className="fh-section-title">From documents to insights in three steps.</h2>
          <div className="fh-grid-3">
            {/* Step 1 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                  <span className="fh-step-num">Step 01</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>POST /upload</span>
                </div>
                <h3 className="fh-card-title">Upload your reports</h3>
                <p className="fh-card-text">
                  Upload one or multiple financial reports in PDF format. Hệ thống tự động nhận diện bảng biểu và cấu
                  trúc mục BCTC.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                  <span className="fh-step-num">Step 02</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>POST /chat/query</span>
                </div>
                <h3 className="fh-card-title">Ask your questions</h3>
                <p className="fh-card-text">
                  Ask about financial figures, ratios, trends, or comparisons in natural language.
                </p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                  <span className="fh-step-num">Step 03</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>GET /file#page</span>
                </div>
                <h3 className="fh-card-title">Explore grounded answers</h3>
                <p className="fh-card-text">
                  Review the response, calculations, and supporting sources with verifiable page citations.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 6. 04 — USE CASES                                                         */}
      {/* ========================================================================= */}
      <section id="use-cases" className="fh-section">
        <div className="fh-container">
          <span className="fh-section-tag">04 — Use Cases</span>
          <h2 className="fh-section-title">Designed for financial research and analysis.</h2>
          <div className="fh-grid-3">
            <div className="fh-card">
              <div className="fh-card-icon">📊</div>
              <h3 className="fh-card-title">Accounting professionals</h3>
              <p className="fh-card-text">
                Find financial figures and analyze financial statements with speed and exact source page validation.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon">🛡️</div>
              <h3 className="fh-card-title">Auditors</h3>
              <p className="fh-card-text">
                Locate supporting information and compare reported figures against disclosures across periods.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon">📈</div>
              <h3 className="fh-card-title">Financial analysts & researchers</h3>
              <p className="fh-card-text">
                Explore company performance across multi-year reports, synthesize ratios, and compare competitors.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 7. 05 — TRUST & TRANSPARENCY                                              */}
      {/* ========================================================================= */}
      <section id="trust" className="fh-section fh-section-alt">
        <div className="fh-container">
          <span className="fh-section-tag">05 — Trust & Transparency</span>
          <h2 className="fh-section-title">Understand where every answer comes from.</h2>
          <p className="fh-section-subtitle">
            Financial analysis requires traceability. We make it easy for users to verify the information behind
            AI-generated answers.
          </p>

          <div className="fh-grid-3">
            <div className="fh-card">
              <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                01. Trích dẫn
              </div>
              <h3 className="fh-card-title">Document citations & source references</h3>
              <p className="fh-card-text">
                Every response references supporting pages directly with clickable highlight jumps.
              </p>
            </div>
            <div className="fh-card">
              <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                02. Minh bạch
              </div>
              <h3 className="fh-card-title">Transparent calculation steps</h3>
              <p className="fh-card-text">
                Constituent arithmetic steps and figures are stated clearly so you can re-check every formula.
              </p>
            </div>
            <div className="fh-card">
              <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                03. Bảo mật
              </div>
              <h3 className="fh-card-title">Data protection & access controls</h3>
              <p className="fh-card-text">
                Workspace notebook isolation ensures your uploaded financial reports remain completely private.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 8. FINAL CTA                                                              */}
      {/* ========================================================================= */}
      <section className="fh-final-cta">
        <div className="fh-container">
          <h2 className="fh-section-title" style={{ fontSize: "38px" }}>
            Ready to explore your financial reports?
          </h2>
          <p className="fh-section-subtitle" style={{ margin: "12px auto 32px" }}>
            Start asking questions and discover insights from your documents.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: "14px", flexWrap: "wrap" }}>
            <button onClick={onEnterApp} className="fh-btn-primary" style={{ padding: "14px 32px", fontSize: "15px" }}>
              Get Started
            </button>
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="fh-btn-secondary"
              style={{ padding: "14px 24px", fontSize: "15px" }}
            >
              Sơ đồ & Test 29 API
            </button>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. FOOTER                                                                 */}
      {/* ========================================================================= */}
      <footer className="fh-footer">
        <div className="fh-footer-inner">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <FinHelpLogo size="sm" />
            <span style={{ color: "#475569" }}>·</span>
            <span>AI-powered Financial Report Assistant</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
            <a href="#features" className="fh-nav-link">
              Features
            </a>
            <a href="#how-it-works" className="fh-nav-link">
              How it works
            </a>
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="fh-nav-link"
              style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
            >
              API Docs
            </button>
          </div>
          <div>© 2026 FinHelp. All rights reserved.</div>
        </div>
      </footer>

      {/* ========================================================================= */}
      {/* API INSPECTOR MODAL WITH LIVE TESTER                                      */}
      {/* ========================================================================= */}
      <ApiInspectorModal
        isOpen={apiModalOpen}
        onClose={() => setApiModalOpen(false)}
        activeEndpoint={activeApiEndpoint}
        onEnterWorkspace={onEnterApp}
      />
    </div>
  );
};

export default LandingPage;
