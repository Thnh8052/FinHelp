import React, { useState, useEffect } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
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
  const { t } = useLanguage();
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
              {t.nav.features}
            </a>
            <a href="#how-it-works" className="fh-nav-link">
              {t.nav.howItWorks}
            </a>
            <a href="#use-cases" className="fh-nav-link">
              {t.nav.useCases}
            </a>
            <a href="#trust" className="fh-nav-link">
              {t.nav.trust}
            </a>
          </nav>

          {/* Right Actions: Live Status, Language Switcher & Auth CTAs */}
          <div className="fh-navbar-actions">
            {/* Live Platform Operational Status */}
            <div
              className="fh-btn-api-map"
              title="FinHelp Platform Status"
            >
              <span className={`fh-status-dot ${systemStatus === "online" ? "online" : "connecting"}`} />
              <span>
                {systemStatus === "online" ? t.common.systemActive : t.common.systemConnecting}
              </span>
            </div>

            {/* Language Switcher Button */}
            <LanguageToggle size="sm" />

            {isAuthenticated ? (
              <button onClick={onEnterApp} className="fh-btn-primary">
                <span>{t.common.openWorkspace}</span>
                <IconArrowRight size={14} />
              </button>
            ) : (
              <>
                <button onClick={() => onOpenAuth("login")} className="fh-btn-text">
                  {t.common.signIn}
                </button>
                <button onClick={onEnterApp} className="fh-btn-primary">
                  {t.common.getStarted}
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
            <span>{t.landing.badge}</span>
          </div>

          {/* Title */}
          <h1 className="fh-hero-title">
            {t.landing.heroTitle1}
            <br />
            <span className="fh-hero-gradient-text">{t.landing.heroTitle2}</span>
          </h1>

          {/* Subtitle */}
          <p className="fh-hero-subtitle">
            {t.landing.heroSubtitle}
          </p>

          {/* Hero CTAs */}
          <div className="fh-hero-actions">
            <button onClick={onEnterApp} className="fh-btn-primary fh-btn-hero-primary">
              <span>{t.common.getStarted}</span>
              <IconArrowRight size={15} />
            </button>
            <a href="#features" className="fh-btn-secondary fh-btn-hero-secondary">
              {t.landing.exploreFeaturesCta}
            </a>
          </div>

          {/* Sample Query Chips (SaaS 2-Line Layout with Horizontal Touch Slider on Mobile) */}
          <div className="fh-chips-container">
            <span className="fh-chips-label">
              {t.landing.trySampleQueries}
            </span>
            <div className="fh-chips-track">
              <button
                type="button"
                onClick={() => setActiveQueryIndex(1)}
                className={`fh-chip ${activeQueryIndex === 1 ? "active" : ""}`}
              >
                <IconCompare size={14} />
                <span>{t.landing.chip1}</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveQueryIndex(2)}
                className={`fh-chip ${activeQueryIndex === 2 ? "active" : ""}`}
              >
                <IconCalculator size={14} />
                <span>{t.landing.chip2}</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveQueryIndex(3)}
                className={`fh-chip ${activeQueryIndex === 3 ? "active" : ""}`}
              >
                <IconSearch size={14} />
                <span>{t.landing.chip3}</span>
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
                {t.landing.previewSessionLabel}
              </span>
            </div>
            <div className="fh-preview-meta-group">
              <div className="fh-badge-wrapper">
                <span className="fh-capability-badge">
                  {t.landing.previewCapability}
                </span>
              </div>
              <span className="fh-preview-filings-badge">
                {t.landing.previewFilingsSelected}
              </span>
            </div>
          </div>

          {/* Q&A Body */}
          <div className="fh-preview-body">
            {/* User Bubble */}
            <div className="fh-user-bubble-wrapper">
              <div className="fh-user-bubble">
                {activeQueryIndex === 1 &&
                  t.landing.query1}
                {activeQueryIndex === 2 &&
                  t.landing.query2}
                {activeQueryIndex === 3 &&
                  t.landing.query3}
              </div>
            </div>

            {/* AI Grounded Answer Card */}
            <div className="fh-ai-response-card">
              <div className="fh-ai-header">
                <div className="fh-ai-title-group">
                  <span className="fh-ai-title-text">{t.landing.aiAnswerTitle}</span>
                </div>
                <span className="fh-ai-grounded-pill">
                  <IconCheck size={12} />
                  <span>{t.landing.groundedPill}</span>
                </span>
              </div>

              {/* Dynamic Answer content */}
              {activeQueryIndex === 1 && (
                <>
                  <p className="fh-ai-answer-lead">
                    {t.landing.answer1Lead}
                  </p>
                  <div className="fh-table-wrapper">
                    <table className="fh-table">
                      <thead>
                        <tr>
                          <th>{t.landing.tableCompany}</th>
                          <th className="fh-table-num">{t.landing.tableFy22}</th>
                          <th className="fh-table-num">{t.landing.tableFy23}</th>
                          <th className="fh-table-num">{t.landing.tableYoy}</th>
                          <th className="fh-table-center">{t.landing.tableRef}</th>
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
                              {t.landing.page45Ref}
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
                              {t.landing.page32Ref}
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
                    {t.landing.answer2Lead}
                  </p>
                  <div className="fh-preview-code-box">
                    <div className="fh-calc-row">
                      <span>{t.landing.cfoLabel}</span>
                      <span className="fh-val-positive">$12,195M</span>
                    </div>
                    <div className="fh-calc-row">
                      <span>{t.landing.capexLabel}</span>
                      <span className="fh-val-negative">-$9,102M</span>
                    </div>
                    <div className="fh-calc-total-row">
                      <span>{t.landing.fcfLabel}</span>
                      <span className="fh-val-positive">+$3,093M</span>
                    </div>
                  </div>
                </>
              )}

              {activeQueryIndex === 3 && (
                <>
                  <p className="fh-ai-answer-lead">
                    {t.landing.answer3Lead}
                  </p>
                  <div className="fh-preview-code-box">
                    <div className="fh-calc-row">
                      <span>{t.landing.receivables1to6}</span>
                      <span className="fh-val-bright">$45.2M (Provision allowance: $12.0M)</span>
                    </div>
                    <div className="fh-calc-row">
                      <span>{t.landing.receivablesOver1yr}</span>
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
                    {t.landing.sourcesTitle}
                  </span>
                  <div className="fh-badge-wrapper">
                    <span className="fh-capability-badge">
                      {t.landing.verifiedCitations}
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
          <span className="fh-section-tag">{t.landing.problemTag}</span>
          <h2 className="fh-section-title">{t.landing.problemTitle}</h2>
          <p className="fh-section-subtitle">
            {t.landing.problemSubtitle}
          </p>

          {/* VISUAL ILLUSTRATION: Before vs After Comparison Graphic */}
          <div className="fh-comparison-wrapper">
            {/* Before Card */}
            <div className="fh-comparison-card fh-comparison-card-before">
              <div className="fh-comparison-header">
                <span className="fh-comparison-title fh-comparison-title-danger">
                  {t.landing.beforeTitle}
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-risk">
                    {t.landing.highErrorRisk}
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc">
                <div className="fh-mockup-meta">
                  <span>{t.landing.beforeDoc}</span>
                  <span>{t.landing.beforeScanned}</span>
                </div>
                <div className="fh-mockup-inner-box">
                  <div className="fh-mockup-strikethrough">
                    {t.landing.beforeStrike}
                  </div>
                  <div className="fh-mockup-muted">
                    {t.landing.beforeMuted}
                  </div>
                </div>
                <div className="fh-mockup-footer">
                  <span className="fh-mockup-alert">{t.landing.beforeSpent}</span>
                  <span className="fh-color-muted">{t.landing.noCitations}</span>
                </div>
              </div>
            </div>

            {/* After Card */}
            <div className="fh-comparison-card fh-comparison-card-after">
              <div className="fh-comparison-header">
                <span className="fh-comparison-title fh-comparison-title-success">
                  {t.landing.afterTitle}
                </span>
                <div className="fh-badge-wrapper">
                  <span className="fh-comparison-badge fh-badge-success">
                    {t.landing.traceableBadge}
                  </span>
                </div>
              </div>
              <div className="fh-mockup-doc fh-mockup-doc-after">
                <div className="fh-mockup-meta-after">
                  <span>{t.landing.afterExtraction}</span>
                  <span className="fh-color-success">{t.landing.verifiedBadge}</span>
                </div>
                <div className="fh-mockup-inner-box-after">
                  <div className="fh-mockup-after-headline">
                    {t.landing.afterDeprec} <span className="fh-val-positive">$1,240.5M</span>
                  </div>
                  <div className="fh-mockup-after-sub">
                    {t.landing.afterGrounded}
                  </div>
                </div>
                <div className="fh-mockup-footer">
                  <span className="fh-mockup-speed">{t.landing.afterSpeed}</span>
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
                    <span className="fh-problem-step">{t.landing.problem1Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.problem1Title}</h3>
                <p className="fh-card-text">
                  {t.landing.problem1Text}
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
                    <span className="fh-problem-step">{t.landing.problem2Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.problem2Title}</h3>
                <p className="fh-card-text">
                  {t.landing.problem2Text}
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
                    <span className="fh-problem-step">{t.landing.problem3Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.problem3Title}</h3>
                <p className="fh-card-text">
                  {t.landing.problem3Text}
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
                    <span className="fh-problem-step">{t.landing.problem4Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.problem4Title}</h3>
                <p className="fh-card-text">
                  {t.landing.problem4Text}
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
              <span className="fh-section-tag">{t.landing.featuresTag}</span>
              <h2 className="fh-section-title">{t.landing.featuresTitle}</h2>
            </div>
            <div className="fh-section-header-side">
              {t.landing.featuresSubtitle}
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
                    {t.landing.bento1Badge}
                  </span>
                </div>
              </div>

              <h3 className="fh-card-title fh-bento-card-title">{t.landing.bento1Title}</h3>
              <p className="fh-bento-card-desc">{t.landing.bento1Desc}</p>

              {/* Visual Table Bounding Mockup */}
              <div className="fh-table-bounding-mockup">
                <div className="fh-table-bounding-header">
                  <span>{t.landing.bento1Header}</span>
                  <span className="fh-color-accent">{t.landing.bento1Tag}</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>{t.landing.bento1Row1}</span>
                  <span className="fh-val-positive">$17,902,400,000</span>
                </div>
                <div className="fh-bounding-box-row">
                  <span>{t.landing.bento1Row2}</span>
                  <span className="fh-color-muted">$10,210,100,000</span>
                </div>
                <div className="fh-bounding-box-row active">
                  <span>{t.landing.bento1Row3}</span>
                  <span className="fh-val-positive">42.96% (+180 bps)</span>
                </div>
              </div>

              <div className="fh-card-footer fh-card-footer-flush">
                {t.landing.bento1Footer}
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
                    {t.landing.bento2Badge}
                  </span>
                </div>
              </div>

              <h3 className="fh-card-title fh-bento-card-title">{t.landing.bento2Title}</h3>
              <p className="fh-bento-card-desc">{t.landing.bento2Desc}</p>

              {/* Visual Split-View Graphic */}
              <div className="fh-split-view-graphic">
                <div className="fh-split-card-ai">
                  <div className="fh-split-card-label">{t.landing.bento2AiLabel}</div>
                  <div className="fh-split-card-body">
                    {t.landing.bento2AiBody}
                  </div>
                  <span className="fh-citation-btn fh-mt-8">{t.landing.bento2PageRef}</span>
                </div>
                <div className="fh-split-card-filing">
                  <div className="fh-split-card-filing-label">{t.landing.bento2FilingLabel}</div>
                  <div className="fh-split-card-highlight">
                    {t.landing.bento2FilingBody}
                  </div>
                </div>
              </div>

              <div className="fh-card-footer fh-card-footer-flush">
                {t.landing.bento2Footer}
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
                      {t.landing.feature1Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.feature1Title}</h3>
                <p className="fh-card-text">
                  {t.landing.feature1Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.feature1Footer}
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
                      {t.landing.feature2Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.feature2Title}</h3>
                <p className="fh-card-text">
                  {t.landing.feature2Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.feature2Footer}
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
                      {t.landing.feature3Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.feature3Title}</h3>
                <p className="fh-card-text">
                  {t.landing.feature3Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.feature3Footer}
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
                      {t.landing.feature4Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.feature4Title}</h3>
                <p className="fh-card-text">
                  {t.landing.feature4Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.feature4Footer}
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
          <span className="fh-section-tag">{t.landing.howTag}</span>
          <h2 className="fh-section-title">{t.landing.howTitle}</h2>
          <p className="fh-section-subtitle">
            {t.landing.howSubtitle}
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
                    <span className="fh-step-num">{t.landing.step1Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.step1Title}</h3>
                <p className="fh-card-text">
                  {t.landing.step1Text}
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
                {t.landing.step1Footer}
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
                    <span className="fh-step-num">{t.landing.step2Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.step2Title}</h3>
                <p className="fh-card-text">
                  {t.landing.step2Text}
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
                {t.landing.step2Footer}
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
                    <span className="fh-step-num">{t.landing.step3Badge}</span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.step3Title}</h3>
                <p className="fh-card-text">
                  {t.landing.step3Text}
                </p>
              </div>
              <div className="fh-card-footer fh-card-footer-muted">
                {t.landing.step3Footer}
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
          <span className="fh-section-tag">{t.landing.useCasesTag}</span>
          <h2 className="fh-section-title">{t.landing.useCasesTitle}</h2>
          <p className="fh-section-subtitle">
            {t.landing.useCasesSubtitle}
          </p>

          {/* Interactive Persona Tabs */}
          <div className="fh-persona-nav">
            <button
              onClick={() => setActivePersona("accounting")}
              className={`fh-persona-tab ${activePersona === "accounting" ? "active" : ""}`}
            >
              <IconAccounting size={16} />
              <span>{t.landing.personaTabAccounting}</span>
            </button>
            <button
              onClick={() => setActivePersona("auditor")}
              className={`fh-persona-tab ${activePersona === "auditor" ? "active" : ""}`}
            >
              <IconAuditor size={16} />
              <span>{t.landing.personaTabAuditor}</span>
            </button>
            <button
              onClick={() => setActivePersona("analyst")}
              className={`fh-persona-tab ${activePersona === "analyst" ? "active" : ""}`}
            >
              <IconAnalyst size={16} />
              <span>{t.landing.personaTabAnalyst}</span>
            </button>
          </div>

          {/* Interactive Persona Content Graphic */}
          <div className="fh-persona-content-card">
            <div>
              {activePersona === "accounting" && (
                <>
                  <div className="fh-persona-tag">
                    {t.landing.persona1Tag}
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    {t.landing.persona1Title}
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    {t.landing.persona1Desc}
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">{t.landing.persona1Chip1}</span>
                    <span className="fh-chip">{t.landing.persona1Chip2}</span>
                  </div>
                </>
              )}
              {activePersona === "auditor" && (
                <>
                  <div className="fh-persona-tag">
                    {t.landing.persona2Tag}
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    {t.landing.persona2Title}
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    {t.landing.persona2Desc}
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">{t.landing.persona2Chip1}</span>
                    <span className="fh-chip">{t.landing.persona2Chip2}</span>
                  </div>
                </>
              )}
              {activePersona === "analyst" && (
                <>
                  <div className="fh-persona-tag">
                    {t.landing.persona3Tag}
                  </div>
                  <h3 className="fh-card-title fh-persona-heading">
                    {t.landing.persona3Title}
                  </h3>
                  <p className="fh-card-text fh-persona-desc">
                    {t.landing.persona3Desc}
                  </p>
                  <div className="fh-persona-chips">
                    <span className="fh-chip">{t.landing.persona3Chip1}</span>
                    <span className="fh-chip">{t.landing.persona3Chip2}</span>
                  </div>
                </>
              )}
            </div>

            {/* Persona Visual Mockup Preview */}
            <div className="fh-persona-preview-box">
              <div className="fh-persona-preview-header">
                <span>{t.landing.personaBoxHeader}</span>
                <span className="fh-color-success">{t.landing.personaGroundedTag}</span>
              </div>
              <div className="fh-persona-query-card">
                {activePersona === "accounting" && t.landing.persona1Query}
                {activePersona === "auditor" && t.landing.persona2Query}
                {activePersona === "analyst" && t.landing.persona3Query}
              </div>
              <div className="fh-persona-result-card">
                <span className="fh-val-positive">{t.landing.personaResultPrefix}</span> {t.landing.personaResultBody}
                <div className="fh-persona-citations">
                  <span className="fh-citation-btn">{t.landing.personaPage45}</span>
                  <span className="fh-citation-btn">{t.landing.personaPage68}</span>
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
          <span className="fh-section-tag">{t.landing.trustTag}</span>
          <h2 className="fh-section-title">{t.landing.trustTitle}</h2>
          <p className="fh-section-subtitle">
            {t.landing.trustSubtitle}
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
                      {t.landing.trust1Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.trust1Title}</h3>
                <p className="fh-card-text">
                  {t.landing.trust1Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.trust1Footer}
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
                      {t.landing.trust2Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.trust2Title}</h3>
                <p className="fh-card-text">
                  {t.landing.trust2Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.trust2Footer}
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
                      {t.landing.trust3Badge}
                    </span>
                  </div>
                </div>
                <h3 className="fh-card-title">{t.landing.trust3Title}</h3>
                <p className="fh-card-text">
                  {t.landing.trust3Text}
                </p>
              </div>
              <div className="fh-card-footer">
                {t.landing.trust3Footer}
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
            {t.landing.finalCtaTitle}
          </h2>
          <p className="fh-section-subtitle fh-cta-subtitle">
            {t.landing.finalCtaSubtitle}
          </p>
          <div className="fh-cta-actions">
            <button onClick={onEnterApp} className="fh-btn-primary fh-btn-cta-primary">
              {t.common.getStarted}
            </button>
            <button
              onClick={onEnterApp}
              className="fh-btn-secondary fh-btn-cta-secondary"
            >
              <span>{t.landing.finalCtaButton2}</span>
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
                {t.landing.footerMission}
              </p>
              <div className="fh-footer-status-wrap">
                <span className="fh-footer-status-pill">
                  <span className="fh-footer-status-dot" />
                  {t.landing.footerStatus}
                </span>
              </div>
            </div>

            {/* Col 2: Platform Capabilities */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">{t.landing.footerPlatformHeading}</div>
              <a href="#features" className="fh-footer-link">{t.landing.footerPlatform1}</a>
              <a href="#features" className="fh-footer-link">{t.landing.footerPlatform2}</a>
              <a href="#features" className="fh-footer-link">{t.landing.footerPlatform3}</a>
              <a href="#features" className="fh-footer-link">{t.landing.footerPlatform4}</a>
              <a href="#features" className="fh-footer-link">{t.landing.footerPlatform5}</a>
            </div>

            {/* Col 3: Use Cases */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">{t.nav.useCases}</div>
              <a href="#use-cases" className="fh-footer-link">{t.landing.footerUseCases1}</a>
              <a href="#use-cases" className="fh-footer-link">{t.landing.footerUseCases2}</a>
              <a href="#use-cases" className="fh-footer-link">{t.landing.footerUseCases3}</a>
              <a href="#use-cases" className="fh-footer-link">{t.landing.footerUseCases4}</a>
              <a href="#trust" className="fh-footer-link">{t.landing.footerUseCases5}</a>
            </div>

            {/* Col 4: Trust & Security */}
            <div className="fh-footer-col">
              <div className="fh-footer-heading">{t.landing.footerSecurityHeading}</div>
              <a href="#trust" className="fh-footer-link">{t.landing.footerSecurity1}</a>
              <a href="#trust" className="fh-footer-link">{t.landing.footerSecurity2}</a>
              <a href="#trust" className="fh-footer-link">{t.landing.footerSecurity3}</a>
              <a href="#trust" className="fh-footer-link">{t.landing.footerSecurity4}</a>
              <a href="#trust" className="fh-footer-link">{t.landing.footerSecurity5}</a>
            </div>
          </div>

          {/* Bottom Sub-row */}
          <div className="fh-footer-bottom">
            <div>
              {t.landing.footerBottomMeta}
            </div>
            <div>{t.landing.footerCopyright}</div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
