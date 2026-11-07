import React, { useState, useEffect } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import { ApiInspectorModal, API_ENDPOINTS_CATALOG, ApiEndpointInfo } from "./ApiInspectorModal";
import {
  IconSearch,
  IconCalculator,
  IconDocuments,
  IconLightbulb,
  IconUpload,
  IconChat,
  IconCompare,
  IconCitation,
  IconHistory,
  IconAccounting,
  IconAuditor,
  IconAnalyst,
  IconLock,
  IconCheck,
  IconArrowRight,
  IconApi,
} from "../../components/common/Icons";
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

  // Bar Style: "floating" (ChatGPT style) vs "dock" (NotebookLM style)
  const [navStyle, setNavStyle] = useState<"floating" | "dock">("floating");

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
        // Offline or proxy error
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
      {/* 1. NAVBAR (Supports both ChatGPT Floating Pill and NotebookLM Dock)       */}
      {/* ========================================================================= */}
      {navStyle === "floating" ? (
        <div className="fh-navbar-floating-wrapper">
          <header className="fh-navbar-floating">
            {/* Logo */}
            <FinHelpLogo
              size="sm"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              className="cursor-pointer"
            />

            {/* Segmented Nav Links */}
            <nav className="fh-nav-pill-group">
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

            {/* Right Actions */}
            <div className="fh-navbar-actions">
              {/* Style Switcher Toggle */}
              <button
                onClick={() => setNavStyle("dock")}
                className="fh-style-toggle-btn"
                title="Switch to NotebookLM style dock bar"
              >
                <span>Bar: Floating</span>
              </button>

              {/* Backend Status Pill */}
              <div
                onClick={() => openApiDetails("/health", "GET")}
                className="fh-btn-api-map cursor-pointer"
                title="FastAPI Backend Health Status (127.0.0.1:8000)"
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
                  {backendStatus === "online" ? `API Online (${backendLatency}ms)` : "29 API Specs"}
                </span>
              </div>

              {isAuthenticated ? (
                <button onClick={onEnterApp} className="fh-btn-primary">
                  <span>Open Workspace</span>
                  <IconArrowRight size={14} />
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
          </header>
        </div>
      ) : (
        <header className="fh-navbar-dock">
          <div className="fh-navbar-dock-inner">
            <FinHelpLogo
              size="sm"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
              className="cursor-pointer"
            />

            <nav className="fh-nav-pill-group">
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

            <div className="fh-navbar-actions">
              <button
                onClick={() => setNavStyle("floating")}
                className="fh-style-toggle-btn"
                title="Switch to ChatGPT style floating pill bar"
              >
                <span>Bar: Dock</span>
              </button>

              <div
                onClick={() => openApiDetails("/health", "GET")}
                className="fh-btn-api-map cursor-pointer"
                title="FastAPI Backend Health Status (127.0.0.1:8000)"
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
                  {backendStatus === "online" ? `API Online (${backendLatency}ms)` : "29 API Specs"}
                </span>
              </div>

              {isAuthenticated ? (
                <button onClick={onEnterApp} className="fh-btn-primary">
                  <span>Open Workspace</span>
                  <IconArrowRight size={14} />
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
      )}

      {/* ========================================================================= */}
      {/* 2. HERO SECTION & PRODUCT PREVIEW                                         */}
      {/* ========================================================================= */}
      <section className="fh-hero fh-grid-pattern">
        <div className="fh-container">
          {/* Badge */}
          <div className="fh-hero-badge">
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor: "#3b82f6",
                display: "inline-block",
              }}
            />
            <span>AI-Powered Financial Intelligence</span>
          </div>

          {/* Title */}
          <h1 className="fh-hero-title">
            Understand Financial Reports.
            <br />
            <span className="fh-hero-gradient-text">Make Better Decisions.</span>
          </h1>

          {/* Subtitle */}
          <p className="fh-hero-subtitle">
            Upload financial statements, ask questions in natural language, and get auditable answers grounded directly in your filings.
          </p>

          {/* Hero CTAs */}
          <div className="fh-hero-actions">
            <button onClick={onEnterApp} className="fh-btn-primary" style={{ padding: "10px 24px", fontSize: "14.5px" }}>
              <span>Get Started</span>
              <IconArrowRight size={15} />
            </button>
            <a href="#features" className="fh-btn-secondary" style={{ padding: "10px 22px", fontSize: "14px" }}>
              Explore Features
            </a>
          </div>

          {/* Sample Query Chips */}
          <div className="fh-chips-container">
            <span style={{ fontSize: "12px", color: "#64748b", fontWeight: 600, marginRight: "4px" }}>
              Try sample queries:
            </span>
            <button
              onClick={() => setActiveQueryIndex(1)}
              className={`fh-chip ${activeQueryIndex === 1 ? "active" : ""}`}
            >
              <IconCompare size={14} />
              <span>YoY Revenue Comparison</span>
            </button>
            <button
              onClick={() => setActiveQueryIndex(2)}
              className={`fh-chip ${activeQueryIndex === 2 ? "active" : ""}`}
            >
              <IconCalculator size={14} />
              <span>Calculate Free Cash Flow</span>
            </button>
            <button
              onClick={() => setActiveQueryIndex(3)}
              className={`fh-chip ${activeQueryIndex === 3 ? "active" : ""}`}
            >
              <IconSearch size={14} />
              <span>Doubtful Debt Footnotes</span>
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
              <span style={{ color: "#94a3b8", fontWeight: 600, fontSize: "11.5px" }}>
                FinHelp Workspace · Session #104
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <button
                onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                className="fh-api-pill fh-api-pill-post"
                title="Inspect API payload and query schema"
              >
                <span>POST /api/v1/chat/query</span>
              </button>
              <span
                style={{
                  padding: "3px 9px",
                  borderRadius: "6px",
                  backgroundColor: "#172554",
                  border: "1px solid #1e40af",
                  color: "#93c5fd",
                  fontSize: "11px",
                  fontWeight: 600,
                }}
              >
                2 filings selected
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
                    (Powered by /chat/query)
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
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <IconCheck size={12} />
                  <span>Grounded in uploaded reports</span>
                </span>
              </div>

              {/* Dynamic Answer content */}
              {activeQueryIndex === 1 && (
                <>
                  <p style={{ margin: 0, fontSize: "13.5px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Company A reported higher revenue growth</strong> over the
                    fiscal period. The comparison is substantiated by the following disclosure lines:
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
                                  "Citation [1]: Company_A_Report.pdf — Page 45 (Consolidated Statement of Income). Direct stream endpoint: GET /api/v1/documents/{document_id}/file#page=45"
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
                                  "Citation [2]: Company_B_Report.pdf — Page 32 (Item 8 Financial Disclosures). Direct stream endpoint: GET /api/v1/documents/{document_id}/file#page=32"
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
                  <p style={{ margin: 0, fontSize: "13.5px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Free Cash Flow (FCF)</strong> is calculated directly from the
                    Consolidated Statement of Cash Flows:
                  </p>
                  <div
                    style={{
                      background: "#080c14",
                      border: "1px solid #1e293b",
                      borderRadius: "10px",
                      padding: "14px 16px",
                      fontSize: "12.5px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: "7px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>(+) Cash Flow from Operating Activities (CFO):</span>
                      <span style={{ color: "#34d399", fontWeight: 700 }}>$12,195M</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>(-) Capital Expenditures (CapEx):</span>
                      <span style={{ color: "#f87171", fontWeight: 700 }}>-$9,102M</span>
                    </div>
                    <div
                      style={{
                        paddingTop: "7px",
                        borderTop: "1px solid #334155",
                        display: "flex",
                        justifyContent: "space-between",
                        color: "#ffffff",
                        fontWeight: 700,
                        fontSize: "13.5px",
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
                  <p style={{ margin: 0, fontSize: "13.5px", lineHeight: "1.6", color: "#cbd5e1" }}>
                    <strong style={{ color: "#ffffff" }}>Footnote Disclosure on Doubtful Accounts:</strong> Overdue trade
                    receivables and provision allowances have been parsed from Note 7:
                  </p>
                  <div
                    style={{
                      background: "#080c14",
                      border: "1px solid #1e293b",
                      borderRadius: "10px",
                      padding: "14px 16px",
                      fontSize: "12.5px",
                      fontFamily: "monospace",
                      display: "flex",
                      flexDirection: "column",
                      gap: "7px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>• Receivables past due 1–6 months:</span>
                      <span style={{ color: "#f8fafc" }}>$45.2M (Provision allowance: $12.0M)</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", color: "#cbd5e1" }}>
                      <span>• Receivables past due &gt; 1 year:</span>
                      <span style={{ color: "#fbbf24", fontWeight: 700 }}>$18.5M (100% reserved)</span>
                    </div>
                  </div>
                </>
              )}

              {/* Citation Alert notification */}
              {activeCitationAlert && (
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "8px",
                    backgroundColor: "rgba(30, 58, 138, 0.45)",
                    border: "1px solid rgba(59, 130, 246, 0.6)",
                    fontSize: "12px",
                    color: "#bfdbfe",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "8px",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <IconCitation size={15} />
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
                    Source references (Audit Trail)
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
          <p className="fh-section-subtitle">
            Traditional financial analysis suffers from tedious manual searching, scattered footnotes, and fragmented comparisons.
          </p>

          <div className="fh-grid-4">
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconSearch size={19} />
              </div>
              <h3 className="fh-card-title">Manual searching</h3>
              <p className="fh-card-text">
                Pinpointing specific figures across hundreds of pages and disclosure footnotes.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconCalculator size={19} />
              </div>
              <h3 className="fh-card-title">Manual calculations</h3>
              <p className="fh-card-text">
                Cross-referencing metrics, margins, and cash flows across multiple fiscal quarters.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconDocuments size={19} />
              </div>
              <h3 className="fh-card-title">Multiple documents</h3>
              <p className="fh-card-text">
                Switching back and forth between separate annual filings to find relevant disclosures.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconLightbulb size={19} />
              </div>
              <h3 className="fh-card-title">Difficult insights</h3>
              <p className="fh-card-text">
                Transforming raw accounting statements into understandable, structured answers.
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
            <div style={{ fontSize: "12.5px", color: "#94a3b8" }}>
              Click any API badge on each feature card to inspect payload specs and test live
            </div>
          </div>

          <div className="fh-grid-3">
            {/* Feature 1 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconUpload size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Document Upload</h3>
                  </div>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/upload/{notebook_id}", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    POST /upload
                  </button>
                </div>
                <p className="fh-card-text">
                  Upload financial reports in PDF format with automatic two-dimensional table recognition and contextual metadata tagging.
                </p>
              </div>
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                Supports: PDF, Form 10-K, Audited Annual Reports
              </div>
            </div>

            {/* Feature 2 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconChat size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>AI-powered Q&amp;A</h3>
                  </div>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    POST /chat/query
                  </button>
                </div>
                <p className="fh-card-text">
                  Ask questions using natural language. Query across complex accounting disclosures without manual page searching.
                </p>
              </div>
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                Interactive Multi-turn Analysis
              </div>
            </div>

            {/* Feature 3 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconCompare size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Multi-report Comparison</h3>
                  </div>
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
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                Cross-compare 2+ companies
              </div>
            </div>

            {/* Feature 4 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconCitation size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Evidence-based Answers</h3>
                  </div>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/{document_id}/file", "GET")}
                    className="fh-api-pill fh-api-pill-get"
                  >
                    GET /documents/&#123;id&#125;/file
                  </button>
                </div>
                <p className="fh-card-text">
                  See the supporting passages and exact document references behind every statement with PDF Split-View jumping.
                </p>
              </div>
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                100% Grounded in Source Filings
              </div>
            </div>

            {/* Feature 5 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconCalculator size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Financial Analysis</h3>
                  </div>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post"
                  >
                    Calculator &amp; Re-check
                  </button>
                </div>
                <p className="fh-card-text">
                  Calculate and interpret margins, growth rates, ratios, and cash flows with automated mathematical verification.
                </p>
              </div>
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                Transparent Arithmetic Steps
              </div>
            </div>

            {/* Feature 6 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div className="fh-card-icon-mono" style={{ margin: 0, width: "32px", height: "32px" }}>
                      <IconHistory size={16} />
                    </div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Conversation History</h3>
                  </div>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/sessions/notebook/{notebook_id}", "GET")}
                    className="fh-api-pill fh-api-pill-get"
                  >
                    GET /chat/sessions
                  </button>
                </div>
                <p className="fh-card-text">
                  Save, search, and continue previous analysis sessions anytime with isolated session history per notebook.
                </p>
              </div>
              <div style={{ marginTop: "14px", paddingTop: "10px", borderTop: "1px solid #1e293b", fontSize: "11.5px", color: "#60a5fa" }}>
                Isolated Notebook Storage
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
          <p className="fh-section-subtitle">
            A seamless workflow designed to eliminate manual data entry and surface verified metrics rapidly.
          </p>

          <div className="fh-grid-3">
            {/* Step 1 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <span className="fh-step-num">Step 01</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>POST /upload</span>
                </div>
                <h3 className="fh-card-title">Upload your reports</h3>
                <p className="fh-card-text">
                  Upload one or multiple financial reports in PDF format. The parsing engine automatically extracts structured financial tables and footnotes.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <span className="fh-step-num">Step 02</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>POST /chat/query</span>
                </div>
                <h3 className="fh-card-title">Ask your questions</h3>
                <p className="fh-card-text">
                  Ask about revenue trends, operating cash flows, liquidity ratios, or footnotes in plain English.
                </p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="fh-card">
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <span className="fh-step-num">Step 03</span>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>GET /file#page</span>
                </div>
                <h3 className="fh-card-title">Explore grounded answers</h3>
                <p className="fh-card-text">
                  Review syntheses, calculations, and supporting source citations side-by-side with split-view PDF navigation.
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
          <p className="fh-section-subtitle">
            Empowering professionals with verifiable data extraction and auditable intelligence.
          </p>

          <div className="fh-grid-3">
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconAccounting size={19} />
              </div>
              <h3 className="fh-card-title">Accounting professionals</h3>
              <p className="fh-card-text">
                Find financial figures and analyze financial statements with speed and exact source page validation.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconAuditor size={19} />
              </div>
              <h3 className="fh-card-title">Auditors</h3>
              <p className="fh-card-text">
                Locate supporting disclosures and compare reported figures against underlying notes across fiscal periods.
              </p>
            </div>
            <div className="fh-card">
              <div className="fh-card-icon-mono">
                <IconAnalyst size={19} />
              </div>
              <h3 className="fh-card-title">Financial analysts &amp; researchers</h3>
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
          <span className="fh-section-tag">05 — Trust &amp; Transparency</span>
          <h2 className="fh-section-title">Understand where every answer comes from.</h2>
          <p className="fh-section-subtitle">
            Financial analysis requires traceability. We make it easy for users to verify the information behind AI-generated answers.
          </p>

          <div className="fh-grid-3">
            <div className="fh-card">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <div className="fh-card-icon-mono" style={{ margin: 0, width: "30px", height: "30px" }}>
                  <IconCitation size={15} />
                </div>
                <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11.5px", textTransform: "uppercase" }}>
                  01. Citations
                </div>
              </div>
              <h3 className="fh-card-title">Document citations &amp; source references</h3>
              <p className="fh-card-text">
                Every response references supporting pages directly with clickable highlight jumps and excerpt validation.
              </p>
            </div>

            <div className="fh-card">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <div className="fh-card-icon-mono" style={{ margin: 0, width: "30px", height: "30px" }}>
                  <IconCalculator size={15} />
                </div>
                <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11.5px", textTransform: "uppercase" }}>
                  02. Arithmetic
                </div>
              </div>
              <h3 className="fh-card-title">Transparent calculation steps</h3>
              <p className="fh-card-text">
                Constituent arithmetic formulas and values are stated clearly so you can re-check every formula and equation.
              </p>
            </div>

            <div className="fh-card">
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <div className="fh-card-icon-mono" style={{ margin: 0, width: "30px", height: "30px" }}>
                  <IconLock size={15} />
                </div>
                <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11.5px", textTransform: "uppercase" }}>
                  03. Security
                </div>
              </div>
              <h3 className="fh-card-title">Data protection &amp; access controls</h3>
              <p className="fh-card-text">
                Workspace notebook isolation ensures your uploaded financial reports remain completely confidential and secure.
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
          <h2 className="fh-section-title" style={{ fontSize: "36px" }}>
            Ready to explore your financial reports?
          </h2>
          <p className="fh-section-subtitle" style={{ margin: "10px auto 28px" }}>
            Start asking questions and discover verifiable insights from your documents.
          </p>
          <div style={{ display: "flex", justifyContent: "center", gap: "12px", flexWrap: "wrap" }}>
            <button onClick={onEnterApp} className="fh-btn-primary" style={{ padding: "12px 28px", fontSize: "14.5px" }}>
              Get Started
            </button>
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="fh-btn-secondary"
              style={{ padding: "12px 22px", fontSize: "14px" }}
            >
              <IconApi size={15} />
              <span>Explore 29 API Endpoints</span>
            </button>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. COMPACT BALANCED FOOTER                                                */}
      {/* ========================================================================= */}
      <footer className="fh-footer">
        <div className="fh-footer-inner">
          <div className="fh-footer-top">
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <FinHelpLogo size="sm" />
              <span style={{ color: "#475569" }}>·</span>
              <span style={{ color: "#94a3b8", fontSize: "12.5px" }}>AI-Powered Financial Intelligence Platform</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
              <a href="#features" className="fh-nav-link" style={{ padding: "4px 8px" }}>
                Features
              </a>
              <a href="#how-it-works" className="fh-nav-link" style={{ padding: "4px 8px" }}>
                How it works
              </a>
              <a href="#use-cases" className="fh-nav-link" style={{ padding: "4px 8px" }}>
                Use Cases
              </a>
              <button
                onClick={() => {
                  setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                  setApiModalOpen(true);
                }}
                className="fh-nav-link"
                style={{ background: "none", border: "none", cursor: "pointer", padding: "4px 8px" }}
              >
                API Specs
              </button>
            </div>
          </div>
          <div className="fh-footer-bottom">
            <div style={{ color: "#64748b" }}>
              FastAPI RAG Engine · Python 3.12 · Qdrant Vector Engine · Docling Table Extraction
            </div>
            <div>© 2026 FinHelp. All rights reserved.</div>
          </div>
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
