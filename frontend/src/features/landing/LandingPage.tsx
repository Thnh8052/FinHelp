import React, { useState, useEffect } from "react";
import { ArrowRight, Check, FileText, Minus, Plus, TrendingUp, TriangleAlert } from "lucide-react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../context/LanguageContext";
import { LanguageToggle } from "../../components/common/LanguageToggle";
import { ThemeToggle } from "../../components/common/ThemeToggle";
import { IconArrowRight } from "../../components/common/Icons";
import "./LandingPage.css";
import "./landing-sections.css";

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
  const { guestQuota } = useAuth();
  const l = t.landing;

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

  const steps = [
    { n: "01", title: l.step1Title, text: l.step1Text },
    { n: "02", title: l.step2Title, text: l.step2Text },
    { n: "03", title: l.step3Title, text: l.step3Text },
  ];
  const trust = [
    { title: l.trust1Title, text: l.trust1Text },
    { title: l.trust2Title, text: l.trust2Text },
    { title: l.trust3Title, text: l.trust3Text },
  ];
  // The guest limits are the account's real quota (read from the backend), never a number written here
  const guestLimit = guestQuota
    ? l.faq1Limit.replace("{docs}", String(guestQuota.max_upload_documents)).replace("{mb}", String(guestQuota.max_file_size_mb))
    : "";
  const faqs = [
    { q: l.faq1Q, a: l.faq1A + guestLimit },
    { q: l.faq2Q, a: l.faq2A },
    { q: l.faq3Q, a: l.faq3A },
    { q: l.faq4Q, a: l.faq4A },
  ];

  const startButtons = (
    <div className="lp-ctas">
      <button type="button" onClick={onEnterApp} className="lp-btn primary lg">
        {l.getStartedCta}
        <ArrowRight size={16} aria-hidden />
      </button>
      <a href="#how-it-works" className="lp-btn outline lg">
        {l.exploreFeaturesCta}
      </a>
    </div>
  );

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
            <a href="#trust" className="fh-nav-link">
              {t.nav.trust}
            </a>
          </nav>

          {/* Right Actions: Live Status, Language Switcher & Auth CTAs */}
          <div className="fh-navbar-actions">
            {/* Live Platform Operational Status */}
            <div
              className="fh-btn-api-map"
              title={l.platformStatus}
            >
              <span className={`fh-status-dot ${systemStatus === "online" ? "online" : "connecting"}`} />
              <span>
                {systemStatus === "online" ? t.common.systemActive : t.common.systemConnecting}
              </span>
            </div>

            {/* Theme and language switches */}
            <ThemeToggle />
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

      <main>
        {/* ======================================================================= */}
        {/* 2. HERO + PRODUCT PREVIEW                                               */}
        {/* ======================================================================= */}
        <section className="lp-hero">
          <span className="lp-pill">{l.badge}</span>
          <h1 className="lp-hero-title">
            {l.heroTitle1}
            <em>{l.heroTitle2}</em>
          </h1>
          <p className="lp-hero-lead">{l.heroSubtitle}</p>
          {startButtons}
          <p className="lp-fine">{l.heroFine}</p>

          {/* A picture of the product, not the product: example data, hidden from screen readers (the sections below say the same in words) */}
          <div className="lp-preview" aria-hidden="true">
            <div className="lp-pv-side">
              <div className="lp-pv-brand">
                <FinHelpLogo size="sm" showText={false} />
                FinHelp
              </div>
              <div className="lp-pv-new">+&nbsp; {l.previewNew}</div>
              <small>{l.previewRecent}</small>
              <div className="lp-pv-chat active">
                {l.previewChat1}
                <span>{l.previewChat1Sub}</span>
              </div>
              <div className="lp-pv-chat">{l.previewChat2}</div>
            </div>

            <div className="lp-pv-main">
              <div className="lp-pv-bar">
                {l.previewTitle}
                <span>{l.previewScope}</span>
              </div>
              <div className="lp-pv-body">
                <div className="lp-pv-q">{l.previewQuestion}</div>
                <div className="lp-pv-a">
                  <b>FinHelp</b>
                  <h4>{l.previewAnswerHead}</h4>
                  <p>{l.previewAnswerBody}</p>
                  <table>
                    <thead>
                      <tr>
                        <th>{l.tableCompany}</th>
                        <th>{l.tableFy22}</th>
                        <th>{l.tableFy23}</th>
                        <th>{l.tableYoy}</th>
                        <th>{l.tableRef}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>{l.demoCompanyA}</strong></td>
                        <td>$14,200M</td>
                        <td>$17,902M</td>
                        <td className="pos">+26.1%</td>
                        <td className="ref">{l.page45Ref}</td>
                      </tr>
                      <tr>
                        <td><strong>{l.demoCompanyB}</strong></td>
                        <td>$28,500M</td>
                        <td>$30,120M</td>
                        <td className="pos">+5.7%</td>
                        <td className="ref">{l.page32Ref}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div className="lp-pv-src">
              <div className="lp-pv-bar">
                {l.previewSourceTitle}
                <span className="ref">{l.page45Ref}</span>
              </div>
              <div className="lp-pv-paper">
                <small>{l.previewPaperKicker}</small>
                <h4>{l.previewPaperTitle}</h4>
                <small>{l.previewPaperUnit}</small>
                <div className="lp-pv-row head"><span /><span>FY2023</span><span>FY2022</span></div>
                <div className="lp-pv-row mark"><span>{l.previewRevenue}</span><span>17,902</span><span>14,200</span></div>
                <div className="lp-pv-row"><span>{l.previewCostRevenue}</span><span>10,473</span><span>8,781</span></div>
              </div>
            </div>
          </div>
          <p className="lp-preview-note">{l.previewCaption}</p>
        </section>

        {/* ======================================================================= */}
        {/* 3. HOW IT WORKS                                                         */}
        {/* ======================================================================= */}
        <section id="how-it-works" className="lp-sec">
          <div className="lp-wrap">
            <h2 className="lp-h2">{l.howTitle}</h2>
            <p className="lp-sub">{l.howSubtitle}</p>
            <ol className="lp-steps">
              {steps.map((s) => (
                <li key={s.n} className="lp-step">
                  <span className="lp-step-n">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ======================================================================= */}
        {/* 4. WHAT IT IS FOR: two capabilities                                     */}
        {/* ======================================================================= */}
        <section id="features" className="lp-sec alt">
          <div className="lp-wrap">
            <p className="lp-eyebrow">{l.featuresTag}</p>
            <div className="lp-cap-head">
              <h2 className="lp-h2">{l.featuresTitle}</h2>
              <p className="lp-sub">{l.featuresSubtitle}</p>
            </div>

            <div className="lp-caps">
              <article className="lp-cap">
                <div className="lp-cap-top">
                  <span className="lp-cap-icon"><TrendingUp size={20} aria-hidden /></span>
                  <div>
                    <h3>{l.cap1Title}</h3>
                    <p>{l.cap1Text}</p>
                  </div>
                </div>
                <div className="lp-cap-pane">
                  <p className="lp-cap-label">{l.cap1Label}</p>
                  <div className="lp-bar">
                    <span>{l.demoCompanyA}</span>
                    <span className="lp-bar-track"><i style={{ width: "100%" }} /></span>
                    <b>26.1%</b>
                  </div>
                  <div className="lp-bar">
                    <span>{l.demoCompanyB}</span>
                    <span className="lp-bar-track"><i className="light" style={{ width: "22%" }} /></span>
                    <b className="muted">5.7%</b>
                  </div>
                </div>
                <p className="lp-cap-foot">{l.cap1Foot}</p>
              </article>

              <article className="lp-cap">
                <div className="lp-cap-top">
                  <span className="lp-cap-icon"><FileText size={20} aria-hidden /></span>
                  <div>
                    <h3>{l.cap2Title}</h3>
                    <p>{l.cap2Text}</p>
                  </div>
                </div>
                <div className="lp-cap-pane">
                  <p className="lp-cap-question">{l.cap2Question}</p>
                  <div className="lp-warn">
                    <TriangleAlert size={18} aria-hidden />
                    <div>
                      <b>{l.cap2WarnTitle}</b>
                      <p>{l.cap2WarnText}</p>
                      <button type="button" className="lp-link" onClick={onEnterApp}>
                        {l.cap2WarnLink}
                        <ArrowRight size={14} aria-hidden />
                      </button>
                    </div>
                  </div>
                </div>
                <p className="lp-cap-foot">{l.cap2Foot}</p>
              </article>
            </div>
          </div>
        </section>

        {/* ======================================================================= */}
        {/* 5. TRUST BAND (navy in both themes)                                     */}
        {/* ======================================================================= */}
        <section id="trust" className="lp-band">
          <div className="lp-wrap lp-band-grid">
            <div>
              <p className="lp-eyebrow on-band">{l.trustTag}</p>
              <h2 className="lp-band-title">{l.trustTitle}</h2>
              <p className="lp-band-text">{l.trustSubtitle}</p>
            </div>
            <ul className="lp-trust">
              {trust.map((x) => (
                <li key={x.title}>
                  <span className="lp-trust-tile"><Check size={18} aria-hidden /></span>
                  <div>
                    <b>{x.title}</b>
                    <span>{x.text}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ======================================================================= */}
        {/* 6. FAQ (native <details>: opens and closes without script)              */}
        {/* ======================================================================= */}
        <section id="faq" className="lp-sec">
          <div className="lp-wrap lp-faq">
            <div>
              <h2 className="lp-h2">{l.faqTitle}</h2>
              <p className="lp-sub">{l.faqSubtitle}</p>
            </div>
            <div>
              {faqs.map((f, i) => (
                <details key={f.q} className="lp-fq" open={i === 0}>
                  <summary>
                    {f.q}
                    <Plus size={18} className="plus" aria-hidden />
                    <Minus size={18} className="minus" aria-hidden />
                  </summary>
                  <p>{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ======================================================================= */}
        {/* 7. CLOSING CALL TO ACTION                                               */}
        {/* ======================================================================= */}
        <section className="lp-cta">
          <div className="lp-wrap">
            <h2 className="lp-cta-title">{l.finalCtaTitle}</h2>
            <p className="lp-cta-sub">{l.finalCtaSubtitle}</p>
            {startButtons}
            <p className="lp-fine">{l.finalCtaNote}</p>
          </div>
        </section>
      </main>

      {/* ========================================================================= */}
      {/* 8. FOOTER                                                                 */}
      {/* ========================================================================= */}
      <footer className="lp-footer">
        <div className="lp-wrap">
          <div className="lp-foot-top">
            <FinHelpLogo size="sm" />
            <span className="lp-foot-tag">{l.footerTagline}</span>
            <nav className="lp-foot-links" aria-label="FinHelp">
              <a href="#how-it-works">{t.nav.howItWorks}</a>
              <a href="#features">{t.nav.features}</a>
              <a href="#trust">{t.nav.trust}</a>
              <button type="button" onClick={() => (isAuthenticated ? onEnterApp() : onOpenAuth("login"))}>
                {isAuthenticated ? t.common.openWorkspace : t.common.signIn}
              </button>
            </nav>
          </div>
          <div className="lp-foot-bottom">
            <span>{l.footerCopyright}</span>
            <span>{l.footerBottomMeta}</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
