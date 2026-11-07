import React, { useState, useEffect } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
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
  // Demo Query Selector in Product Preview
  const [activeQueryIndex, setActiveQueryIndex] = useState<number>(1);
  const [activeCitationAlert, setActiveCitationAlert] = useState<string | null>(null);

  // Interactive Persona Tab in Section 04
  const [activePersona, setActivePersona] = useState<"accounting" | "auditor" | "analyst">("accounting");

  // System Status Check (Simple Operational Indicator)
  const [systemStatus, setSystemStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    let isMounted = true;
    const checkHealth = async () => {
      try {
        const res = await fetch("/health", { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          if (isMounted) setSystemStatus("online");
          return;
        }
      } catch {
        // Offline or proxy error
      }
      if (isMounted) setSystemStatus("offline");
    };
    checkHealth();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="fh-landing-root">
      {/* Background radial glow */}
      <div className="fh-hero-glow" />

      {/* ========================================================================= */}
      {/* 1. PERMANENT FLOATING PILL NAVBAR (ChatGPT Sites Style)                   */}
      {/* ========================================================================= */}
      <div className="fh-navbar-floating-wrapper">
        <header className="fh-navbar-floating">
          {/* Logo with clean emblem and generous spacing */}
          <FinHelpLogo
            size="sm"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="cursor-pointer"
          />

          {/* Segmented Capsule Nav Links */}
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

          {/* Right Actions: Live Status & Auth CTAs */}
          <div className="fh-navbar-actions">
            {/* Live Platform Operational Status */}
            <div
              className="fh-btn-api-map"
              title="FinHelp Platform Status"
            >
              <span
                style={{
                  width: "7px",
                  height: "7px",
                  borderRadius: "50%",
                  backgroundColor: systemStatus === "online" ? "#10b981" : "#f59e0b",
                  display: "inline-block",
                }}
              />
              <span>
                {systemStatus === "online" ? "System Active" : "Connecting..."}
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

      {/* ========================================================================= */}
      {/* 2. HERO SECTION & PRODUCT PREVIEW                                         */}
      {/* ========================================================================= */}
      <section className="fh-hero fh-grid-pattern">
        <div className="fh-container">
          {/* Tagline Badge */}
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

          {/* Sample Query Chips (2-Row Balanced SaaS Layout) */}
          <div className="fh-chips-container">
            <div className="fh-chips-row fh-chips-row-1">
              <span className="fh-chips-label">
                Try sample queries:
              </span>
              <button
                onClick={() => setActiveQueryIndex(1)}
                className={`fh-chip ${activeQueryIndex === 1 ? "active" : ""}`}
              >
                <IconCompare size={14} />
                <span>YoY Revenue Comparison</span>
              </button>
            </div>
            <div className="fh-chips-row fh-chips-row-2">
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
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
              <div className="fh-badge-wrapper">
                <span className="fh-capability-badge">
                  Natural Language Analysis
                </span>
              </div>
              <span
                style={{
                  padding: "3px 9px",
                  borderRadius: "6px",
                  backgroundColor: "#172554",
                  border: "1px solid #1e40af",
                  color: "#93c5fd",
                  fontSize: "11px",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
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
                                  "Citation [1]: Company_A_Report.pdf — Page 45 (Consolidated Statement of Income)."
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
                                  "Citation [2]: Company_B_Report.pdf — Page 32 (Item 8 Financial Disclosures)."
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
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "6px" }}>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      Verified Citations
                    </span>
                  </div>
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
      {/* 3. 01 — THE PROBLEM (With Visual Before vs After Split Illustration)       */}
      {/* ========================================================================= */}
      <section className="fh-section fh-section-alt">
        <div className="fh-container">
          <span className="fh-section-tag">01 — The Problem</span>
          <h2 className="fh-section-title">Financial reports are complex and time-consuming to analyze.</h2>
          <p className="fh-section-subtitle">
            Traditional financial research is fragmented across scanned PDFs, footnotes, and disparate accounting filings.
          </p>

          {/* VISUAL ILLUSTRATION: Before vs After Comparison Graphic */}
          <div className="fh-comparison-wrapper">
            {/* Before Card */}
            <div className="fh-comparison-card fh-comparison-card-before">
              <div className="fh-comparison-header">
                <span className="fh-comparison-title" style={{ color: "#f87171" }}>
                  Before: Manual Financial Audit
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-risk">
                    High Error Risk
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc">
                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
                  <span>Form 10-K Annual Report (142 pages)</span>
                  <span>Scanned PDF</span>
                </div>
                <div style={{ padding: "8px", background: "#0c101c", borderRadius: "6px", border: "1px dashed #334155" }}>
                  <div style={{ color: "#fca5a5", textDecoration: "line-through" }}>
                    Depreciation expense: $1,240M (?) [Note 14 vs Cash Flow mismatch]
                  </div>
                  <div style={{ color: "#64748b", marginTop: "4px" }}>
                    Manual search across footnotes 12, 14, and Consolidated Statement...
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "4px" }}>
                  <span style={{ color: "#ef4444", fontSize: "11px" }}>⚠️ 4.5 hours spent verifying numbers</span>
                  <span style={{ color: "#64748b" }}>No verified citations</span>
                </div>
              </div>
            </div>

            {/* After Card */}
            <div className="fh-comparison-card fh-comparison-card-after">
              <div className="fh-comparison-header">
                <span className="fh-comparison-title" style={{ color: "#60a5fa" }}>
                  After: FinHelp Grounded Intelligence
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-success">
                    100% Traceable
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc" style={{ background: "#050b18", borderColor: "#1e3a8a" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "#93c5fd" }}>
                  <span>Automated Tabular Extraction Engine</span>
                  <span style={{ color: "#34d399" }}>✓ Verified</span>
                </div>
                <div style={{ padding: "8px", background: "#091428", borderRadius: "6px", border: "1px solid rgba(59, 130, 246, 0.4)" }}>
                  <div style={{ color: "#ffffff", fontWeight: 600 }}>
                    Depreciation &amp; Amortization: <span style={{ color: "#34d399" }}>$1,240.5M</span>
                  </div>
                  <div style={{ color: "#93c5fd", fontSize: "11px", marginTop: "2px" }}>
                    Grounded in Note 14 (Fixed Assets, p. 68) &amp; Operating Cash Flow (p. 48)
                  </div>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "4px" }}>
                  <span style={{ color: "#38bdf8", fontSize: "11px" }}>⚡ 12 seconds with exact page jump</span>
                  <span className="fh-citation-btn">[1] #page=68</span>
                </div>
              </div>
            </div>
          </div>

          {/* 4 Standardized Feature Cards with Identical 38x38px Icons */}
          <div className="fh-grid-4">
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconSearch size={18} />
                  </div>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>01. SEARCH</span>
                </div>
                <h3 className="fh-card-title">Manual searching</h3>
                <p className="fh-card-text">
                  Pinpointing specific figures across hundreds of pages and disclosure footnotes.
                </p>
              </div>
            </div>

            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCalculator size={18} />
                  </div>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>02. MATH</span>
                </div>
                <h3 className="fh-card-title">Manual calculations</h3>
                <p className="fh-card-text">
                  Cross-referencing metrics, margins, and cash flows across multiple fiscal quarters.
                </p>
              </div>
            </div>

            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconDocuments size={18} />
                  </div>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>03. FILINGS</span>
                </div>
                <h3 className="fh-card-title">Multiple documents</h3>
                <p className="fh-card-text">
                  Switching back and forth between separate annual filings to find relevant disclosures.
                </p>
              </div>
            </div>

            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconLightbulb size={18} />
                  </div>
                  <span style={{ fontSize: "11px", color: "#64748b", fontFamily: "monospace" }}>04. INSIGHTS</span>
                </div>
                <h3 className="fh-card-title">Difficult insights</h3>
                <p className="fh-card-text">
                  Transforming raw accounting statements into understandable, structured answers.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 4. 02 — CORE FEATURES (With Visual Bento Showcase Grid)                    */}
      {/* ========================================================================= */}
      <section id="features" className="fh-section">
        <div className="fh-container">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <span className="fh-section-tag">02 — Core Features</span>
              <h2 className="fh-section-title">Everything you need to explore financial reports.</h2>
            </div>
            <div style={{ fontSize: "12.5px", color: "#94a3b8" }}>
              Comprehensive tools built for high-stakes financial research, multi-filing comparisons, and precision.
            </div>
          </div>

          {/* VISUAL BENTO SHOWCASE GRID */}
          <div className="fh-bento-hero-grid">
            {/* Bento Visual 1: Document Ingestion with Table Bounding Boxes */}
            <div className="fh-bento-visual-card">
              <div className="fh-card-header">
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div className="fh-card-icon-mono">
                    <IconUpload size={18} />
                  </div>
                  <div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Document Upload &amp; Tabular Extraction</h3>
                    <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>Intelligent Layout &amp; Table Structure Recognition</p>
                  </div>
                </div>
                <div className="fh-badge-wrapper">
                  <span className="fh-capability-badge">
                    Automated Ingestion
                  </span>
                </div>
              </div>

              {/* Visual Table Bounding Mockup */}
              <div className="fh-table-bounding-mockup">
                <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b", padding: "0 6px", fontSize: "11px" }}>
                  <span>FINANCIAL STATEMENT BOUNDING EXTRACTION</span>
                  <span style={{ color: "#60a5fa" }}>High-Density Context</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>[Table 1.1] Consolidated Net Revenue</span>
                  <span style={{ color: "#34d399", fontWeight: 700 }}>$17,902,400,000</span>
                </div>
                <div className="fh-bounding-box-row">
                  <span>[Table 1.2] Cost of Goods Sold (COGS)</span>
                  <span style={{ color: "#94a3b8" }}>$10,210,100,000</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>[Table 1.3] Gross Operating Margin</span>
                  <span style={{ color: "#60a5fa", fontWeight: 700 }}>42.96% (+180 bps)</span>
                </div>
              </div>

              <div className="fh-card-footer" style={{ margin: 0, borderTop: "none", paddingTop: 0 }}>
                Supports: PDF, Form 10-K, Audited Annual Reports
              </div>
            </div>

            {/* Bento Visual 2: PDF Split-View Citation Grounding */}
            <div className="fh-bento-visual-card">
              <div className="fh-card-header">
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div className="fh-card-icon-mono">
                    <IconCitation size={18} />
                  </div>
                  <div>
                    <h3 className="fh-card-title" style={{ margin: 0 }}>Split-View Citation Jumping</h3>
                    <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>100% Grounded in Underlying Documents</p>
                  </div>
                </div>
                <div className="fh-badge-wrapper">
                  <span className="fh-capability-badge">
                    Split-View Inspection
                  </span>
                </div>
              </div>

              {/* Visual Split-View Graphic */}
              <div className="fh-split-view-graphic">
                <div style={{ padding: "8px", background: "#0c1222", borderRadius: "8px", border: "1px solid #1e3a8a" }}>
                  <div style={{ color: "#93c5fd", fontWeight: 600, marginBottom: "4px" }}>AI Response:</div>
                  <div style={{ color: "#cbd5e1", lineHeight: "1.4" }}>
                    Net sales expanded 26.1% YoY to $17,902M...
                  </div>
                  <span className="fh-citation-btn" style={{ marginTop: "8px" }}>[1] Page 45</span>
                </div>
                <div style={{ padding: "8px", background: "#060912", borderRadius: "8px", border: "1px solid #334155" }}>
                  <div style={{ color: "#64748b", marginBottom: "4px" }}>Filing: Item 8 (p. 45)</div>
                  <div style={{ background: "rgba(59, 130, 246, 0.2)", border: "1px dashed #60a5fa", borderRadius: "4px", padding: "4px", color: "#ffffff" }}>
                    "...net revenue reached $17,902M for fiscal 2023."
                  </div>
                </div>
              </div>

              <div className="fh-card-footer" style={{ margin: 0, borderTop: "none", paddingTop: 0 }}>
                Direct Stream: Original Document Page 45
              </div>
            </div>
          </div>

          {/* 4 Standardized Feature Cards Below Bento with Unified 38x38px Icons */}
          <div className="fh-grid-4" style={{ marginTop: "20px" }}>
            {/* Feature 1 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconChat size={18} />
                  </div>
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      Interactive Q&amp;A
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">AI-powered Q&amp;A</h3>
                <p className="fh-card-text">
                  Ask questions using natural language. Query across complex accounting disclosures without manual page searching.
                </p>
              </div>
              <div className="fh-card-footer">
                Interactive Multi-turn Analysis
              </div>
            </div>

            {/* Feature 2 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCompare size={18} />
                  </div>
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      Cross-Entity
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">Multi-report Comparison</h3>
                <p className="fh-card-text">
                  Compare companies, fiscal periods, and financial indicators across multiple filings simultaneously.
                </p>
              </div>
              <div className="fh-card-footer">
                Cross-compare 2+ companies
              </div>
            </div>

            {/* Feature 3 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCalculator size={18} />
                  </div>
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      Deterministic Math
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">Financial Analysis</h3>
                <p className="fh-card-text">
                  Calculate and interpret margins, growth rates, ratios, and cash flows with automated mathematical verification.
                </p>
              </div>
              <div className="fh-card-footer">
                Transparent Arithmetic Steps
              </div>
            </div>

            {/* Feature 4 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconHistory size={18} />
                  </div>
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      Isolated Vault
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">Conversation History</h3>
                <p className="fh-card-text">
                  Save, search, and continue previous analysis sessions anytime with isolated session history per notebook.
                </p>
              </div>
              <div className="fh-card-footer">
                Isolated Notebook Storage
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 5. 03 — HOW IT WORKS (With Pipeline Visual Progression)                   */}
      {/* ========================================================================= */}
      <section id="how-it-works" className="fh-section fh-section-alt">
        <div className="fh-container">
          <span className="fh-section-tag">03 — How It Works</span>
          <h2 className="fh-section-title">From documents to insights in three steps.</h2>
          <p className="fh-section-subtitle">
            A verified pipeline engineered to eliminate manual data entry and surface auditable metrics rapidly.
          </p>

          <div className="fh-grid-3">
            {/* Step 1 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconUpload size={18} />
                  </div>
                  <span className="fh-step-num">Step 01</span>
                </div>
                <h3 className="fh-card-title">Upload your reports</h3>
                <p className="fh-card-text">
                  Upload one or multiple financial reports in PDF format. Our ingestion pipeline parses complex two-dimensional tables, text blocks, and footnotes into structured data.
                </p>
              </div>
              <div className="fh-card-footer" style={{ color: "#94a3b8" }}>
                Instant Document Ingestion
              </div>
            </div>

            {/* Step 2 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconChat size={18} />
                  </div>
                  <span className="fh-step-num">Step 02</span>
                </div>
                <h3 className="fh-card-title">Ask your questions</h3>
                <p className="fh-card-text">
                  Query in natural language. FinHelp cross-references financial statements, disclosures, and auditor notes to isolate verified context.
                </p>
              </div>
              <div className="fh-card-footer" style={{ color: "#94a3b8" }}>
                Contextual Semantic Synthesis
              </div>
            </div>

            {/* Step 3 */}
            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCitation size={18} />
                  </div>
                  <span className="fh-step-num">Step 03</span>
                </div>
                <h3 className="fh-card-title">Explore grounded answers</h3>
                <p className="fh-card-text">
                  Review synthesized metrics, arithmetic steps, and click citation badges to jump directly to corresponding PDF pages in split-view.
                </p>
              </div>
              <div className="fh-card-footer" style={{ color: "#94a3b8" }}>
                Interactive Audit Trail
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 6. 04 — USE CASES (With Interactive Persona Workflow Switcher)            */}
      {/* ========================================================================= */}
      <section id="use-cases" className="fh-section">
        <div className="fh-container">
          <span className="fh-section-tag">04 — Use Cases</span>
          <h2 className="fh-section-title">Designed for financial research and analysis.</h2>
          <p className="fh-section-subtitle">
            Tailored workflows empowering accountants, auditors, and equity analysts with verifiable document intelligence.
          </p>

          {/* Interactive Persona Tabs */}
          <div className="fh-persona-nav">
            <button
              onClick={() => setActivePersona("accounting")}
              className={`fh-persona-tab ${activePersona === "accounting" ? "active" : ""}`}
            >
              <IconAccounting size={16} />
              <span>Accounting Professionals</span>
            </button>
            <button
              onClick={() => setActivePersona("auditor")}
              className={`fh-persona-tab ${activePersona === "auditor" ? "active" : ""}`}
            >
              <IconAuditor size={16} />
              <span>Auditors &amp; Regulators</span>
            </button>
            <button
              onClick={() => setActivePersona("analyst")}
              className={`fh-persona-tab ${activePersona === "analyst" ? "active" : ""}`}
            >
              <IconAnalyst size={16} />
              <span>Financial Analysts</span>
            </button>
          </div>

          {/* Interactive Persona Content Graphic */}
          <div className="fh-persona-content-card">
            <div>
              {activePersona === "accounting" && (
                <>
                  <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                    Persona: Corporate Accounting
                  </div>
                  <h3 className="fh-card-title" style={{ fontSize: "20px" }}>
                    Accelerate financial statement reconciliations
                  </h3>
                  <p className="fh-card-text" style={{ fontSize: "14px", marginTop: "8px" }}>
                    Instantly extract line items across Balance Sheets and Cash Flows. Verify footnote adjustments, tax provisions, and lease liabilities with single-click page validation.
                  </p>
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span className="fh-chip">GAAP / IFRS Footnotes</span>
                    <span className="fh-chip">Intercompany Eliminations</span>
                  </div>
                </>
              )}
              {activePersona === "auditor" && (
                <>
                  <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                    Persona: Statutory Audit &amp; Compliance
                  </div>
                  <h3 className="fh-card-title" style={{ fontSize: "20px" }}>
                    Cross-examine reported figures with zero hallucination
                  </h3>
                  <p className="fh-card-text" style={{ fontSize: "14px", marginTop: "8px" }}>
                    Trace every reported disclosure back to the original auditor notes. Automatically verify arithmetic consistency between consolidated tables and note breakdowns.
                  </p>
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span className="fh-chip">Substantive Testing</span>
                    <span className="fh-chip">Footnote Audit Trail</span>
                  </div>
                </>
              )}
              {activePersona === "analyst" && (
                <>
                  <div style={{ color: "#60a5fa", fontWeight: 700, fontSize: "12px", textTransform: "uppercase", marginBottom: "6px" }}>
                    Persona: Equity Research &amp; M&amp;A
                  </div>
                  <h3 className="fh-card-title" style={{ fontSize: "20px" }}>
                    Benchmark competitors across multi-year cycles
                  </h3>
                  <p className="fh-card-text" style={{ fontSize: "14px", marginTop: "8px" }}>
                    Select filings from multiple companies and evaluate margin expansion, Free Cash Flow yields, and leverage metrics side-by-side in seconds.
                  </p>
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <span className="fh-chip">YoY Peer Benchmarking</span>
                    <span className="fh-chip">FCF Yield Modeling</span>
                  </div>
                </>
              )}
            </div>

            {/* Persona Visual Mockup Preview */}
            <div style={{ background: "#060912", border: "1px solid #1e293b", borderRadius: "12px", padding: "18px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", fontSize: "11px", color: "#64748b" }}>
                <span>SAMPLE QUERY &amp; AUDIT TRAIL</span>
                <span style={{ color: "#10b981" }}>● Grounded Answer</span>
              </div>
              <div style={{ padding: "10px", background: "#0e1526", borderRadius: "8px", border: "1px solid #1e3a8a", fontSize: "12.5px", color: "#cbd5e1", marginBottom: "10px" }}>
                {activePersona === "accounting" && "Q: Reconcile Operating Income to EBITDA including depreciation notes."}
                {activePersona === "auditor" && "Q: Cross-check Note 8 contingent liabilities against balance sheet reserves."}
                {activePersona === "analyst" && "Q: Compare FY23 Free Cash Flow margin between Company A and Company B."}
              </div>
              <div style={{ padding: "10px", background: "#080c14", borderRadius: "8px", fontSize: "12px", color: "#94a3b8" }}>
                <span style={{ color: "#34d399", fontWeight: 700 }}>Calculation Output:</span> Matches reported Note details with 100% audit confidence.
                <div style={{ display: "flex", gap: "6px", marginTop: "8px" }}>
                  <span className="fh-citation-btn">[1] Page 45</span>
                  <span className="fh-citation-btn">[2] Page 68</span>
                </div>
              </div>
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
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCitation size={18} />
                  </div>
                  <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11px", textTransform: "uppercase" }}>
                    01. Citations
                  </span>
                </div>
                <h3 className="fh-card-title">Document citations &amp; source references</h3>
                <p className="fh-card-text">
                  Every response references supporting pages directly with clickable highlight jumps and excerpt validation.
                </p>
              </div>
              <div className="fh-card-footer">
                Interactive PDF Highlighting
              </div>
            </div>

            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconCalculator size={18} />
                  </div>
                  <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11px", textTransform: "uppercase" }}>
                    02. Arithmetic
                  </span>
                </div>
                <h3 className="fh-card-title">Transparent calculation steps</h3>
                <p className="fh-card-text">
                  Constituent arithmetic formulas and values are stated clearly so you can re-check every formula and equation.
                </p>
              </div>
              <div className="fh-card-footer">
                Auditable Math Proofs
              </div>
            </div>

            <div className="fh-card">
              <div>
                <div className="fh-card-header">
                  <div className="fh-card-icon-mono">
                    <IconLock size={18} />
                  </div>
                  <span style={{ color: "#60a5fa", fontWeight: 700, fontSize: "11px", textTransform: "uppercase" }}>
                    03. Security
                  </span>
                </div>
                <h3 className="fh-card-title">Data protection &amp; access controls</h3>
                <p className="fh-card-text">
                  Workspace notebook isolation ensures your uploaded financial reports remain completely confidential and secure.
                </p>
              </div>
              <div className="fh-card-footer">
                Notebook Isolation
              </div>
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
              onClick={onEnterApp}
              className="fh-btn-secondary"
              style={{ padding: "12px 24px", fontSize: "14px" }}
            >
              <span>Explore Sample Workspace</span>
            </button>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. EXPANDED, BALANCED 4-COLUMN FOOTER                                     */}
      {/* ========================================================================= */}
      <footer className="fh-footer">
        <div className="fh-footer-inner">
          <div className="fh-footer-grid">
            {/* Col 1: Brand & Mission */}
            <div className="fh-footer-col">
              <FinHelpLogo size="sm" />
              <p style={{ margin: "8px 0 0 0", color: "#94a3b8", fontSize: "13px", lineHeight: "1.6", maxWidth: "340px" }}>
                AI-Powered Financial Intelligence Platform. Empowering accounting, audit, and equity research professionals with auditable document extraction.
              </p>
              <div style={{ marginTop: "12px" }}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    padding: "4px 10px",
                    borderRadius: "9999px",
                    backgroundColor: "rgba(16, 185, 129, 0.12)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    color: "#34d399",
                    fontSize: "11px",
                  }}
                >
                  <span style={{ width: "6px", height: "6px", borderRadius: "50%", backgroundColor: "#10b981" }} />
                  All Systems Operational
                </span>
              </div>
            </div>

            {/* Col 2: Platform Capabilities */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">Platform</div>
              <a href="#features" className="fh-footer-link">Document Ingestion</a>
              <a href="#features" className="fh-footer-link">Interactive Workspace Chat</a>
              <a href="#features" className="fh-footer-link">Multi-Report Comparison</a>
              <a href="#features" className="fh-footer-link">PDF Split-View Jumping</a>
              <a href="#features" className="fh-footer-link">Mathematical Engine</a>
            </div>

            {/* Col 3: Use Cases */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">Use Cases</div>
              <a href="#use-cases" className="fh-footer-link">Accounting Professionals</a>
              <a href="#use-cases" className="fh-footer-link">Statutory Auditors</a>
              <a href="#use-cases" className="fh-footer-link">Financial Analysts &amp; M&amp;A</a>
              <a href="#use-cases" className="fh-footer-link">SEC Form 10-K Analysis</a>
              <a href="#trust" className="fh-footer-link">Audit Trail &amp; Provenance</a>
            </div>

            {/* Col 4: Trust & Security */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">Security &amp; Standards</div>
              <a href="#trust" className="fh-footer-link">SOC-2 Type II Certified</a>
              <a href="#trust" className="fh-footer-link">256-Bit Bank-Grade Encryption</a>
              <a href="#trust" className="fh-footer-link">Isolated Workspace Sandboxes</a>
              <a href="#trust" className="fh-footer-link">Zero-Data-Retention Architecture</a>
              <a href="#trust" className="fh-footer-link">Auditable Source Verification</a>
            </div>
          </div>

          {/* Bottom Sub-row */}
          <div className="fh-footer-bottom">
            <div>
              FinHelp Financial Intelligence Platform · SOC-2 Ready · Zero Data Retention Architecture
            </div>
            <div>© 2026 FinHelp Inc. All rights reserved.</div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
