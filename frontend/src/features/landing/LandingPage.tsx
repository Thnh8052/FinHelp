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

          {/* Direct Nav Links with Balanced Spacing (SaaS Minimalist Layout) */}
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

          {/* Right Actions: Live Status & Auth CTAs */}
          <div className="fh-navbar-actions">
            {/* Live Platform Operational Status */}
            <div
              className="fh-btn-api-map"
              title="FinHelp Platform Status"
            >
              <span className={`fh-status-dot ${systemStatus === "online" ? "online" : "connecting"}`} />
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
            <span className="fh-hero-badge-dot" />
            <span>AI-Powered Financial Intelligence</span>
          </div>

          {/* Title */}
          <h1 className="fh-hero-title">
            Understand Financial Reports
            <br />
            <span className="fh-hero-gradient-text">Make Better Decisions</span>
          </h1>

          {/* Subtitle */}
          <p className="fh-hero-subtitle">
            Upload financial statements, ask questions in natural language, and get auditable answers grounded directly in your filings.
          </p>

          {/* Hero CTAs */}
          <div className="fh-hero-actions">
            <button onClick={onEnterApp} className="fh-btn-primary fh-btn-hero-primary">
              <span>Get Started</span>
              <IconArrowRight size={15} />
            </button>
            <a href="#features" className="fh-btn-secondary fh-btn-hero-secondary">
              Explore Features
            </a>
          </div>

          {/* Sample Query Chips (SaaS 2-Line Layout with Horizontal Touch Slider on Mobile) */}
          <div className="fh-chips-container">
            <span className="fh-chips-label">
              Try sample queries:
            </span>
            <div className="fh-chips-track">
              <button
                type="button"
                onClick={() => setActiveQueryIndex(1)}
                className={`fh-chip ${activeQueryIndex === 1 ? "active" : ""}`}
              >
                <IconCompare size={14} />
                <span>YoY Revenue Comparison</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveQueryIndex(2)}
                className={`fh-chip ${activeQueryIndex === 2 ? "active" : ""}`}
              >
                <IconCalculator size={14} />
                <span>Calculate Free Cash Flow</span>
              </button>
              <button
                type="button"
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
            <div className="fh-preview-title-group">
              <div className="fh-window-dots">
                <span className="fh-dot fh-dot-red" />
                <span className="fh-dot fh-dot-yellow" />
                <span className="fh-dot fh-dot-green" />
              </div>
              <span className="fh-preview-session-label">
                FinHelp Workspace · Session #104
              </span>
            </div>
            <div className="fh-preview-meta-group">
              <div className="fh-badge-wrapper">
                <span className="fh-capability-badge">
                  Natural Language Analysis
                </span>
              </div>
              <span className="fh-preview-filings-badge">
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
                <div className="fh-ai-title-group">
                  <span className="fh-ai-title-text">AI-generated answer</span>
                </div>
                <span className="fh-ai-grounded-pill">
                  <IconCheck size={12} />
                  <span>Grounded in uploaded reports</span>
                </span>
              </div>

              {/* Dynamic Answer content */}
              {activeQueryIndex === 1 && (
                <>
                  <p className="fh-ai-answer-lead">
                    <strong className="fh-color-white">Company A reported higher revenue growth</strong> over the
                    fiscal period. The comparison is substantiated by the following disclosure lines:
                  </p>
                  <div className="fh-table-wrapper">
                    <table className="fh-table">
                      <thead>
                        <tr>
                          <th>Company</th>
                          <th className="fh-table-num">FY22 Revenue</th>
                          <th className="fh-table-num">FY23 Revenue</th>
                          <th className="fh-table-num">YoY Growth</th>
                          <th className="fh-table-center">Reference</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td className="fh-table-company-name">Company A</td>
                          <td className="fh-table-val-muted">$14,200M</td>
                          <td className="fh-table-val-highlight">$17,902M</td>
                          <td className="fh-table-val-highlight">+26.1%</td>
                          <td className="fh-table-center">
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
                          <td className="fh-table-company-name">Company B</td>
                          <td className="fh-table-val-muted">$28,500M</td>
                          <td className="fh-table-val-neutral">$30,120M</td>
                          <td className="fh-table-val-neutral">+5.7%</td>
                          <td className="fh-table-center">
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
                  <p className="fh-ai-answer-lead">
                    <strong className="fh-color-white">Free Cash Flow (FCF)</strong> is calculated directly from the
                    Consolidated Statement of Cash Flows:
                  </p>
                  <div className="fh-preview-code-box">
                    <div className="fh-calc-row">
                      <span>(+) Cash Flow from Operating Activities (CFO):</span>
                      <span className="fh-val-positive">$12,195M</span>
                    </div>
                    <div className="fh-calc-row">
                      <span>(-) Capital Expenditures (CapEx):</span>
                      <span className="fh-val-negative">-$9,102M</span>
                    </div>
                    <div className="fh-calc-total-row">
                      <span>(=) Free Cash Flow (FCF):</span>
                      <span className="fh-val-positive">+$3,093M</span>
                    </div>
                  </div>
                </>
              )}

              {activeQueryIndex === 3 && (
                <>
                  <p className="fh-ai-answer-lead">
                    <strong className="fh-color-white">Footnote Disclosure on Doubtful Accounts:</strong> Overdue trade
                    receivables and provision allowances have been parsed from Note 7:
                  </p>
                  <div className="fh-preview-code-box">
                    <div className="fh-calc-row">
                      <span>• Receivables past due 1–6 months:</span>
                      <span className="fh-val-bright">$45.2M (Provision allowance: $12.0M)</span>
                    </div>
                    <div className="fh-calc-row">
                      <span>• Receivables past due &gt; 1 year:</span>
                      <span className="fh-val-warning">$18.5M (100% reserved)</span>
                    </div>
                  </div>
                </>
              )}

              {/* Citation Alert notification */}
              {activeCitationAlert && (
                <div className="fh-citation-alert">
                  <div className="fh-citation-alert-content">
                    <IconCitation size={15} />
                    <span>{activeCitationAlert}</span>
                  </div>
                  <button
                    onClick={() => setActiveCitationAlert(null)}
                    className="fh-citation-alert-close"
                  >
                    ✕
                  </button>
                </div>
              )}

              {/* Source references footer */}
              <div className="fh-sources-box">
                <div className="fh-sources-header">
                  <span className="fh-sources-title">
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
                    <span className="fh-source-page">#page=45</span>
                  </div>
                  <div className="fh-source-item">
                    <span>
                      <strong>[2]</strong> Company_B_Report.pdf — Page 32 (Item 8 Financials)
                    </span>
                    <span className="fh-source-page">#page=32</span>
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
                <span className="fh-comparison-title fh-comparison-title-danger">
                  Before: Manual Financial Audit
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-risk">
                    High Error Risk
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc">
                <div className="fh-mockup-meta">
                  <span>Form 10-K Annual Report (142 pages)</span>
                  <span>Scanned PDF</span>
                </div>
                <div className="fh-mockup-inner-box">
                  <div className="fh-mockup-strikethrough">
                    Depreciation expense: $1,240M (?) [Note 14 vs Cash Flow mismatch]
                  </div>
                  <div className="fh-mockup-muted">
                    Manual search across footnotes 12, 14, and Consolidated Statement...
                  </div>
                </div>
                <div className="fh-mockup-footer">
                  <span className="fh-mockup-alert">⚠️ 4.5 hours spent verifying numbers</span>
                  <span className="fh-color-muted">No verified citations</span>
                </div>
              </div>
            </div>

            {/* After Card */}
            <div className="fh-comparison-card fh-comparison-card-after">
              <div className="fh-comparison-header">
                <span className="fh-comparison-title fh-comparison-title-success">
                  After: FinHelp Grounded Intelligence
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-success">
                    100% Traceable
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc fh-mockup-doc-after">
                <div className="fh-mockup-meta-after">
                  <span>Automated Tabular Extraction Engine</span>
                  <span className="fh-color-success">✓ Verified</span>
                </div>
                <div className="fh-mockup-inner-box-after">
                  <div className="fh-mockup-after-headline">
                    Depreciation &amp; Amortization: <span className="fh-val-positive">$1,240.5M</span>
                  </div>
                  <div className="fh-mockup-after-sub">
                    Grounded in Note 14 (Fixed Assets, p. 68) &amp; Operating Cash Flow (p. 48)
                  </div>
                </div>
                <div className="fh-mockup-footer">
                  <span className="fh-mockup-speed">⚡ 12 seconds with exact page jump</span>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-problem-step">01. SEARCH</span>
                  </div>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-problem-step">02. MATH</span>
                  </div>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-problem-step">03. FILINGS</span>
                  </div>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-problem-step">04. INSIGHTS</span>
                  </div>
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
          <div className="fh-section-header-split">
            <div>
              <span className="fh-section-tag">02 — Core Features</span>
              <h2 className="fh-section-title">Everything you need to explore financial reports.</h2>
            </div>
            <div className="fh-section-header-side">
              Comprehensive tools built for high-stakes financial research, multi-filing comparisons, and precision.
            </div>
          </div>

          {/* VISUAL BENTO SHOWCASE GRID */}
          <div className="fh-bento-hero-grid">
            {/* Bento Visual 1: Document Ingestion with Table Bounding Boxes */}
            <div className="fh-bento-visual-card">
              <div className="fh-card-header">
                <div className="fh-card-icon-mono">
                  <IconUpload size={18} />
                </div>
                <div className="fh-badge-wrapper">
                  <span className="fh-capability-badge">
                    Automated Ingestion
                  </span>
                </div>
              </div>

              <h3 className="fh-card-title fh-bento-card-title">Document Upload &amp; Tabular Extraction</h3>
              <p className="fh-bento-card-desc">Intelligent Layout &amp; Table Structure Recognition</p>

              {/* Visual Table Bounding Mockup */}
              <div className="fh-table-bounding-mockup">
                <div className="fh-table-bounding-header">
                  <span>FINANCIAL STATEMENT BOUNDING EXTRACTION</span>
                  <span className="fh-color-accent">High-Density Context</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>[Table 1.1] Consolidated Net Revenue</span>
                  <span className="fh-val-positive">$17,902,400,000</span>
                </div>
                <div className="fh-bounding-box-row">
                  <span>[Table 1.2] Cost of Goods Sold (COGS)</span>
                  <span className="fh-color-muted">$10,210,100,000</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>[Table 1.3] Gross Operating Margin</span>
                  <span className="fh-val-positive">42.96% (+180 bps)</span>
                </div>
              </div>

              <div className="fh-card-footer fh-card-footer-flush">
                Supports: PDF, Form 10-K, Audited Annual Reports
              </div>
            </div>

            {/* Bento Visual 2: PDF Split-View Citation Grounding */}
            <div className="fh-bento-visual-card">
              <div className="fh-card-header">
                <div className="fh-card-icon-mono">
                  <IconCitation size={18} />
                </div>
                <div className="fh-badge-wrapper">
                  <span className="fh-capability-badge">
                    Split-View Inspection
                  </span>
                </div>
              </div>

              <h3 className="fh-card-title fh-bento-card-title">Split-View Citation Jumping</h3>
              <p className="fh-bento-card-desc">100% Grounded in Underlying Documents</p>

              {/* Visual Split-View Graphic */}
              <div className="fh-split-view-graphic">
                <div className="fh-split-card-ai">
                  <div className="fh-split-card-label">AI Response:</div>
                  <div className="fh-split-card-body">
                    Net sales expanded 26.1% YoY to $17,902M...
                  </div>
                  <span className="fh-citation-btn fh-mt-8">[1] Page 45</span>
                </div>
                <div className="fh-split-card-filing">
                  <div className="fh-split-card-filing-label">Filing: Item 8 (p. 45)</div>
                  <div className="fh-split-card-highlight">
                    "...net revenue reached $17,902M for fiscal 2023."
                  </div>
                </div>
              </div>

              <div className="fh-card-footer fh-card-footer-flush">
                Direct Stream: Original Document Page 45
              </div>
            </div>
          </div>

          {/* 4 Standardized Feature Cards Below Bento with Unified 38x38px Icons */}
          <div className="fh-grid-4 fh-mt-20">
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-step-num">Step 01</span>
                  </div>
                </div>
                <h3 className="fh-card-title">Upload your reports</h3>
                <p className="fh-card-text">
                  Upload one or multiple financial reports in PDF format. Our ingestion pipeline parses complex two-dimensional tables, text blocks, and footnotes into structured data.
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-step-num">Step 02</span>
                  </div>
                </div>
                <h3 className="fh-card-title">Ask your questions</h3>
                <p className="fh-card-text">
                  Query in natural language. FinHelp cross-references financial statements, disclosures, and auditor notes to isolate verified context.
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-step-num">Step 03</span>
                  </div>
                </div>
                <h3 className="fh-card-title">Explore grounded answers</h3>
                <p className="fh-card-text">
                  Review synthesized metrics, arithmetic steps, and click citation badges to jump directly to corresponding PDF pages in split-view.
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
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
                  <div className="fh-persona-tag">
                    Persona: Corporate Accounting
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    Accelerate financial statement reconciliations
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    Instantly extract line items across Balance Sheets and Cash Flows. Verify footnote adjustments, tax provisions, and lease liabilities with single-click page validation.
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">GAAP / IFRS Footnotes</span>
                    <span className="fh-chip">Intercompany Eliminations</span>
                  </div>
                </>
              )}
              {activePersona === "auditor" && (
                <>
                  <div className="fh-persona-tag">
                    Persona: Statutory Audit &amp; Compliance
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    Cross-examine reported figures with zero hallucination
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    Trace every reported disclosure back to the original auditor notes. Automatically verify arithmetic consistency between consolidated tables and note breakdowns.
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">Substantive Testing</span>
                    <span className="fh-chip">Footnote Audit Trail</span>
                  </div>
                </>
              )}
              {activePersona === "analyst" && (
                <>
                  <div className="fh-persona-tag">
                    Persona: Equity Research &amp; M&amp;A
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    Benchmark competitors across multi-year cycles
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    Select filings from multiple companies and evaluate margin expansion, Free Cash Flow yields, and leverage metrics side-by-side in seconds.
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">YoY Peer Benchmarking</span>
                    <span className="fh-chip">FCF Yield Modeling</span>
                  </div>
                </>
              )}
            </div>

            {/* Persona Visual Mockup Preview */}
            <div className="fh-persona-preview-box">
              <div className="fh-persona-preview-header">
                <span>SAMPLE QUERY &amp; AUDIT TRAIL</span>
                <span className="fh-color-success">● Grounded Answer</span>
              </div>
              <div className="fh-persona-query-card">
                {activePersona === "accounting" && "Q: Reconcile Operating Income to EBITDA including depreciation notes."}
                {activePersona === "auditor" && "Q: Cross-check Note 8 contingent liabilities against balance sheet reserves."}
                {activePersona === "analyst" && "Q: Compare FY23 Free Cash Flow margin between Company A and Company B."}
              </div>
              <div className="fh-persona-result-card">
                <span className="fh-val-positive">Calculation Output:</span> Matches reported Note details with 100% audit confidence.
                <div className="fh-persona-citations">
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-trust-badge">
                      01. Citations
                    </span>
                  </div>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-trust-badge">
                      02. Arithmetic
                    </span>
                  </div>
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
                  <div className="fh-badge-wrapper">
                    <span className="fh-trust-badge">
                      03. Security
                    </span>
                  </div>
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
          <h2 className="fh-section-title fh-cta-title">
            Ready to explore your financial reports?
          </h2>
          <p className="fh-section-subtitle fh-cta-subtitle">
            Start asking questions and discover verifiable insights from your documents.
          </p>
          <div className="fh-cta-actions">
            <button onClick={onEnterApp} className="fh-btn-primary fh-btn-cta-primary">
              Get Started
            </button>
            <button
              onClick={onEnterApp}
              className="fh-btn-secondary fh-btn-cta-secondary"
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
              <p className="fh-footer-desc">
                AI-Powered Financial Intelligence Platform. Empowering accounting, audit, and equity research professionals with auditable document extraction.
              </p>
              <div className="fh-footer-status-wrap">
                <span className="fh-footer-status-pill">
                  <span className="fh-footer-status-dot" />
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
