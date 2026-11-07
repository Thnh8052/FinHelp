import React, { useState } from "react";
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

  const openApiDetails = (path: string, method: "POST" | "GET" | "PATCH" | "DELETE" = "POST") => {
    const ep = API_ENDPOINTS_CATALOG.find((item) => item.path === path && item.method === method);
    if (ep) {
      setActiveApiEndpoint(ep);
    }
    setApiModalOpen(true);
  };

  return (
    <div className="fh-landing-root">
      {/* Background glow & subtle grid */}
      <div className="fh-hero-glow" />

      {/* ========================================================================= */}
      {/* 1. NAVBAR                                                                 */}
      {/* ========================================================================= */}
      <header className="sticky top-0 z-40 backdrop-blur-md bg-[#0B0F19]/90 border-b border-slate-800/80 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto h-16 flex items-center justify-between">
          {/* Brand Logo with New Emblem */}
          <FinHelpLogo
            size="md"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="cursor-pointer"
          />

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-white transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-white transition-colors">
              How it works
            </a>
            <a href="#use-cases" className="hover:text-white transition-colors">
              Use Cases
            </a>
            <a href="#trust" className="hover:text-white transition-colors">
              Trust
            </a>
          </nav>

          {/* Right Actions: API Map & Auth / Workspace CTA */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-medium text-blue-400 bg-blue-500/10 border border-blue-500/30 hover:bg-blue-500/20 transition-all"
              title="Xem sơ đồ liên kết API backend tương ứng với giao diện"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              <span>Sơ đồ API</span>
            </button>

            {isAuthenticated ? (
              <button
                onClick={onEnterApp}
                className="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-600/30 flex items-center gap-1.5 transition-all"
              >
                <span>Vào Không Gian Phân Tích</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            ) : (
              <>
                <button
                  onClick={() => onOpenAuth("login")}
                  className="text-xs sm:text-sm font-medium text-slate-300 hover:text-white px-3 py-1.5 transition-colors"
                >
                  Sign in
                </button>
                <button
                  onClick={onEnterApp}
                  className="px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-md shadow-blue-600/30 transition-all"
                >
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
      <section className="relative pt-16 sm:pt-24 pb-16 text-center fh-grid-pattern px-4">
        <div className="max-w-4xl mx-auto">
          {/* Tagline */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold mb-6">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            <span>AI-powered Financial Analysis</span>
          </div>

          {/* Heading */}
          <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-[1.14] fh-heading">
            Understand Financial Reports.
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-300 to-sky-400">
              Make Better Decisions.
            </span>
          </h1>

          {/* Subtitle */}
          <p className="mt-6 text-base sm:text-lg text-slate-400 max-w-2xl mx-auto leading-relaxed fh-finance-text">
            Upload financial reports, ask questions in natural language, and get answers grounded in your documents.
          </p>

          {/* CTA Buttons */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3.5">
            <button
              onClick={onEnterApp}
              className="w-full sm:w-auto px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm shadow-xl shadow-blue-600/30 flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <span>Get Started</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </button>
            <a
              href="#features"
              className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 text-slate-300 border border-slate-700 font-medium text-sm transition-all inline-flex items-center justify-center"
            >
              Explore Features
            </a>
          </div>

          {/* Interactive Question Suggestions */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2 max-w-2xl mx-auto">
            <span className="text-xs text-slate-500 font-semibold mr-1">Thử câu hỏi mẫu:</span>
            <button
              onClick={() => setActiveQueryIndex(1)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeQueryIndex === 1
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              📈 So sánh doanh thu YoY
            </button>
            <button
              onClick={() => setActiveQueryIndex(2)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeQueryIndex === 2
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              💰 Tính Free Cash Flow
            </button>
            <button
              onClick={() => setActiveQueryIndex(3)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                activeQueryIndex === 3
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              🔍 Thuyết minh Dự phòng nợ
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* PRODUCT PREVIEW SHOWCASE (Centered, Grounded Answer with Citations)       */}
        {/* ========================================================================= */}
        <div className="max-w-5xl mx-auto mt-12 text-left">
          <div className="rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl fh-glow-blue overflow-hidden">
            {/* Window Topbar */}
            <div className="px-5 py-3 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-slate-700" />
                <span className="w-3 h-3 rounded-full bg-slate-700" />
                <span className="w-3 h-3 rounded-full bg-slate-700" />
                <span className="text-slate-400 font-medium ml-2">FinHelp Workspace · Session #104</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                  className="fh-api-pill fh-api-pill-post"
                  title="Bấm để xem đặc tả API gửi câu hỏi"
                >
                  <span>POST /api/v1/chat/query</span>
                </button>
                <div className="px-2.5 py-1 rounded bg-blue-950 text-blue-300 border border-blue-800/80 font-medium text-[11px]">
                  2 reports selected
                </div>
              </div>
            </div>

            {/* Q&A Content Area */}
            <div className="p-6 space-y-5 bg-slate-900/90 text-sm">
              {/* Question Bubble */}
              <div className="flex justify-end">
                <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-xs sm:text-sm font-medium max-w-xl">
                  {activeQueryIndex === 1 &&
                    "Compare the revenue growth of these two companies and show the main financial drivers."}
                  {activeQueryIndex === 2 &&
                    "Calculate Free Cash Flow (FCF = Cash from Operations - CapEx) for the latest fiscal year."}
                  {activeQueryIndex === 3 &&
                    "Check the footnote disclosure on allowances for doubtful accounts and trade receivables."}
                </div>
              </div>

              {/* Grounded Answer Card */}
              <div className="bg-slate-950/90 border border-slate-800 rounded-2xl p-5 space-y-4">
                <div className="flex items-center justify-between text-xs pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-400 font-medium">AI-generated answer</span>
                    <button
                      onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                      className="text-[10px] text-blue-400 underline font-mono cursor-pointer"
                    >
                      (Xử lý bởi /chat/query)
                    </button>
                  </div>
                  <span className="text-emerald-400 font-medium flex items-center gap-1 text-[11px]">
                    ✓ Grounded in uploaded reports
                  </span>
                </div>

                {/* Query 1: Revenue comparison */}
                {activeQueryIndex === 1 && (
                  <>
                    <p className="text-xs sm:text-sm text-slate-300 leading-relaxed fh-finance-text">
                      <strong className="text-white">Company A reported higher revenue growth</strong> over the fiscal
                      period. The answer is supported by the relevant figures and references in the uploaded reports:
                    </p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase tracking-wider">
                            <th className="py-2">Company</th>
                            <th className="py-2 text-right">FY22 Revenue</th>
                            <th className="py-2 text-right">FY23 Revenue</th>
                            <th className="py-2 text-right">YoY Growth</th>
                            <th className="py-2 text-center">Reference</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60 fh-mono text-[12px]">
                          <tr>
                            <td className="py-2.5 font-sans font-medium text-slate-200">Company A</td>
                            <td className="py-2.5 text-right">$14,200M</td>
                            <td className="py-2.5 text-right text-emerald-400 font-semibold">$17,902M</td>
                            <td className="py-2.5 text-right text-emerald-400 font-semibold">+26.1%</td>
                            <td className="py-2.5 text-center font-sans">
                              <button
                                onClick={() =>
                                  setActiveCitationAlert(
                                    "Trích dẫn [1]: Company_A_Report.pdf — Trang 45 (Báo cáo Kết quả Kinh doanh Hợp nhất). Endpoint xem file gốc: GET /api/v1/documents/{id}/raw#page=45"
                                  )
                                }
                                className="px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300 text-[11px] hover:bg-blue-900 cursor-pointer transition-colors"
                              >
                                [1] Page 45
                              </button>
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 font-sans font-medium text-slate-200">Company B</td>
                            <td className="py-2.5 text-right">$28,500M</td>
                            <td className="py-2.5 text-right text-slate-300">$30,120M</td>
                            <td className="py-2.5 text-right text-slate-300">+5.7%</td>
                            <td className="py-2.5 text-center font-sans">
                              <button
                                onClick={() =>
                                  setActiveCitationAlert(
                                    "Trích dẫn [2]: Company_B_Report.pdf — Trang 32 (Item 8 Financial Disclosures). Endpoint xem file gốc: GET /api/v1/documents/{id}/raw#page=32"
                                  )
                                }
                                className="px-2 py-0.5 rounded bg-blue-950 border border-blue-800 text-blue-300 text-[11px] hover:bg-blue-900 cursor-pointer transition-colors"
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

                {/* Query 2: Free Cash Flow */}
                {activeQueryIndex === 2 && (
                  <>
                    <p className="text-xs sm:text-sm text-slate-300 leading-relaxed fh-finance-text">
                      <strong className="text-white">Free Cash Flow (FCF)</strong> được tính toán trực tiếp từ Báo cáo
                      Lưu chuyển tiền tệ hợp nhất:
                    </p>
                    <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 fh-mono text-xs space-y-2">
                      <div className="flex justify-between text-slate-300">
                        <span>(+) Lưu chuyển tiền từ HĐ kinh doanh (CFO):</span>
                        <span className="text-emerald-400 font-bold">$12,195M</span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>(-) Chi mua sắm TSCĐ (CapEx):</span>
                        <span className="text-red-400 font-bold">-$9,102M</span>
                      </div>
                      <div className="pt-2 border-t border-slate-700/80 flex justify-between text-white font-bold text-sm">
                        <span>(=) Free Cash Flow (FCF):</span>
                        <span className="text-emerald-400 font-bold">+$3,093M</span>
                      </div>
                    </div>
                  </>
                )}

                {/* Query 3: Provision for doubtful accounts */}
                {activeQueryIndex === 3 && (
                  <>
                    <p className="text-xs sm:text-sm text-slate-300 leading-relaxed fh-finance-text">
                      <strong className="text-white">Thuyết minh Dự phòng nợ phải thu khó đòi:</strong> Hệ thống đã bóc
                      tách chi tiết dư nợ quá hạn và mức trích lập tương ứng:
                    </p>
                    <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 fh-mono text-xs space-y-1.5">
                      <div className="flex justify-between text-slate-300">
                        <span>• Nợ quá hạn 1–6 tháng:</span>
                        <span className="text-slate-200">$45.2M (Đã trích lập $12.0M)</span>
                      </div>
                      <div className="flex justify-between text-slate-300">
                        <span>• Nợ quá hạn trên 1 năm:</span>
                        <span className="text-amber-400 font-bold">$18.5M (Đã trích lập 100%)</span>
                      </div>
                    </div>
                  </>
                )}

                {/* Citation Feedback Alert */}
                {activeCitationAlert && (
                  <div className="p-3 rounded-xl bg-blue-950/80 border border-blue-700/60 text-xs text-blue-200 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-blue-400">📄</span>
                      <span>{activeCitationAlert}</span>
                    </div>
                    <button
                      onClick={() => setActiveCitationAlert(null)}
                      className="text-slate-400 hover:text-white ml-2 text-xs font-bold"
                    >
                      ✕
                    </button>
                  </div>
                )}

                {/* Source references footer */}
                <div className="pt-3 border-t border-slate-800 text-xs">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
                      Source references (Trích dẫn kiểm chứng)
                    </span>
                    <button
                      onClick={() => openApiDetails("/api/v1/documents/{id}/raw", "GET")}
                      className="fh-api-pill fh-api-pill-get text-[10px]"
                    >
                      <span>GET /api/v1/documents/&#123;id&#125;/raw</span>
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center justify-between">
                      <span>
                        <strong>[1]</strong> Company_A_Report.pdf — Page 45 (Income Statement)
                      </span>
                      <span className="text-[10px] text-blue-400 font-mono">#page=45</span>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center justify-between">
                      <span>
                        <strong>[2]</strong> Company_B_Report.pdf — Page 32 (Item 8 Financials)
                      </span>
                      <span className="text-[10px] text-blue-400 font-mono">#page=32</span>
                    </div>
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
      <section className="py-20 border-t border-slate-800 bg-slate-950/40 px-4">
        <div className="max-w-6xl mx-auto">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">01 — The Problem</span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2 fh-heading">
            Financial reports are complex and time-consuming to analyze.
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-10 text-xs sm:text-sm">
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 fh-card">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold mb-3 text-base">
                🔍
              </div>
              <h3 className="font-bold text-white mb-2">Manual searching</h3>
              <p className="text-slate-400 leading-relaxed fh-finance-text">
                Finding specific figures across lengthy reports and disclosure footnotes.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 fh-card">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold mb-3 text-base">
                🧮
              </div>
              <h3 className="font-bold text-white mb-2">Manual calculations</h3>
              <p className="text-slate-400 leading-relaxed fh-finance-text">
                Comparing financial metrics across multiple fiscal quarters and periods.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 fh-card">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold mb-3 text-base">
                📑
              </div>
              <h3 className="font-bold text-white mb-2">Multiple documents</h3>
              <p className="text-slate-400 leading-relaxed fh-finance-text">
                Switching between separate annual filings to find relevant disclosures.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 fh-card">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold mb-3 text-base">
                💡
              </div>
              <h3 className="font-bold text-white mb-2">Difficult insights</h3>
              <p className="text-slate-400 leading-relaxed fh-finance-text">
                Turning raw accounting statements into understandable, structured answers.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 4. 02 — CORE FEATURES (With Interactive API Badges)                       */}
      {/* ========================================================================= */}
      <section id="features" className="py-20 border-t border-slate-800 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-400">02 — Core Features</span>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2 fh-heading">
                Everything you need to explore financial reports.
              </h2>
            </div>
            <div className="text-xs text-slate-400">
              <span>Bấm vào thẻ API trên từng tính năng để xem chi tiết kết nối</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10 text-xs sm:text-sm">
            {/* Feature 1 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">Document Upload</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/upload", "POST")}
                    className="fh-api-pill fh-api-pill-post text-[10px]"
                  >
                    POST /documents/upload
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  Upload financial reports in PDF format with automatic table recognition and contextual metadata
                  tagging.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Hỗ trợ: PDF, Form 10-K, BCTC Kiểm toán</span>
              </div>
            </div>

            {/* Feature 2 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">AI-powered Q&A</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post text-[10px]"
                  >
                    POST /chat/query
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  Ask questions using natural language. Query across complex accounting disclosures without manual page
                  searching.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Trực tiếp trên Workspace Chat</span>
              </div>
            </div>

            {/* Feature 3 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">Multi-report Comparison</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post text-[10px]"
                  >
                    Multi-document scope
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  Compare companies, fiscal periods, and financial indicators across multiple filings simultaneously.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Đối chiếu chéo 2+ công ty</span>
              </div>
            </div>

            {/* Feature 4 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">Evidence-based Answers</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/documents/{id}/raw", "GET")}
                    className="fh-api-pill fh-api-pill-get text-[10px]"
                  >
                    GET /documents/&#123;id&#125;/raw
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  See the supporting passages and exact document references behind every statement with PDF Split-View
                  jumping.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Xác minh số liệu gốc 100%</span>
              </div>
            </div>

            {/* Feature 5 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">Financial Analysis</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/query", "POST")}
                    className="fh-api-pill fh-api-pill-post text-[10px]"
                  >
                    Calculator & Re-check
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  Calculate and interpret margins, growth rates, ratios, and cash flows with automated mathematical
                  verification.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Công thức toán học minh bạch</span>
              </div>
            </div>

            {/* Feature 6 */}
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-white text-base">Conversation History</h3>
                  <button
                    onClick={() => openApiDetails("/api/v1/chat/sessions", "GET")}
                    className="fh-api-pill fh-api-pill-get text-[10px]"
                  >
                    GET /chat/sessions
                  </button>
                </div>
                <p className="text-slate-400 leading-relaxed fh-finance-text">
                  Save, search, and continue previous analysis sessions anytime with isolated session history per
                  notebook.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-blue-400">
                <span>Lưu trữ phiên an toàn</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 5. 03 — HOW IT WORKS                                                      */}
      {/* ========================================================================= */}
      <section id="how-it-works" className="py-20 border-t border-slate-800 bg-slate-950/40 px-4">
        <div className="max-w-6xl mx-auto">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">03 — How It Works</span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2 fh-heading">
            From documents to insights in three steps.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            {/* Step 1 */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs fh-mono font-bold text-blue-400 bg-blue-950 px-2.5 py-1 rounded-full border border-blue-800">
                  Step 01
                </span>
                <span className="text-[10px] text-slate-500 font-mono">POST /upload</span>
              </div>
              <h3 className="text-base font-bold text-white mt-3 mb-2">Upload your reports</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Upload one or multiple financial reports in PDF format. Hệ thống tự động nhận diện bảng biểu và cấu
                trúc.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs fh-mono font-bold text-blue-400 bg-blue-950 px-2.5 py-1 rounded-full border border-blue-800">
                  Step 02
                </span>
                <span className="text-[10px] text-slate-500 font-mono">POST /chat/query</span>
              </div>
              <h3 className="text-base font-bold text-white mt-3 mb-2">Ask your questions</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Ask about financial figures, ratios, trends, or comparisons in natural language.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs fh-mono font-bold text-blue-400 bg-blue-950 px-2.5 py-1 rounded-full border border-blue-800">
                  Step 03
                </span>
                <span className="text-[10px] text-slate-500 font-mono">GET /raw#page</span>
              </div>
              <h3 className="text-base font-bold text-white mt-3 mb-2">Explore grounded answers</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Review the response, calculations, and supporting sources with verifiable page citations.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 6. 04 — USE CASES                                                         */}
      {/* ========================================================================= */}
      <section id="use-cases" className="py-20 border-t border-slate-800 px-4">
        <div className="max-w-6xl mx-auto">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">04 — Use Cases</span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2 fh-heading">
            Designed for financial research and analysis.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-10">
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold mb-4 text-lg">
                📊
              </div>
              <h3 className="font-bold text-white text-base mb-2">Accounting professionals</h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed fh-finance-text">
                Find financial figures and analyze financial statements with speed and exact source page validation.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold mb-4 text-lg">
                🛡️
              </div>
              <h3 className="font-bold text-white text-base mb-2">Auditors</h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed fh-finance-text">
                Locate supporting information and compare reported figures against disclosures across periods.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900/50 border border-slate-800 fh-card">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold mb-4 text-lg">
                📈
              </div>
              <h3 className="font-bold text-white text-base mb-2">Financial analysts & researchers</h3>
              <p className="text-xs sm:text-sm text-slate-400 leading-relaxed fh-finance-text">
                Explore company performance across multi-year reports, synthesize ratios, and compare competitors.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 7. 05 — TRUST & TRANSPARENCY                                              */}
      {/* ========================================================================= */}
      <section id="trust" className="py-20 border-t border-slate-800 bg-slate-950/40 px-4">
        <div className="max-w-6xl mx-auto">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">05 — Trust & Transparency</span>
          <h2 className="text-2xl sm:text-3xl font-extrabold text-white mt-2 fh-heading">
            Understand where every answer comes from.
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-2 max-w-2xl fh-finance-text">
            Financial analysis requires traceability. We make it easy for users to verify the information behind
            AI-generated answers.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8">
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="text-blue-400 font-bold text-xs uppercase mb-1">01. Trích dẫn</div>
              <h3 className="font-bold text-white text-sm mb-2">Document citations & source references</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Every response references supporting pages directly with clickable highlight jumps.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="text-blue-400 font-bold text-xs uppercase mb-1">02. Minh bạch</div>
              <h3 className="font-bold text-white text-sm mb-2">Transparent calculation steps</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Constituent arithmetic steps and figures are stated clearly so you can re-check every formula.
              </p>
            </div>
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 fh-card">
              <div className="text-blue-400 font-bold text-xs uppercase mb-1">03. Bảo mật</div>
              <h3 className="font-bold text-white text-sm mb-2">Data protection & access controls</h3>
              <p className="text-xs text-slate-400 leading-relaxed fh-finance-text">
                Workspace notebook isolation ensures your uploaded financial reports remain completely private.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 8. FINAL CTA                                                              */}
      {/* ========================================================================= */}
      <section className="py-20 border-t border-slate-800 text-center px-4">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white fh-heading">
            Ready to explore your financial reports?
          </h2>
          <p className="mt-3 text-slate-400 text-sm fh-finance-text">
            Start asking questions and discover insights from your documents.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <button
              onClick={onEnterApp}
              className="px-7 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-sm shadow-xl shadow-blue-600/30 transition-all cursor-pointer"
            >
              Get Started
            </button>
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="px-5 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs font-mono font-medium transition-all"
            >
              Sơ đồ API Backend
            </button>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* 9. FOOTER                                                                 */}
      {/* ========================================================================= */}
      <footer className="py-10 border-t border-slate-800 bg-[#070A12] text-xs text-slate-500 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <FinHelpLogo size="sm" />
            <span className="text-slate-600 hidden sm:inline">·</span>
            <span className="text-slate-400">AI-powered Financial Report Assistant</span>
          </div>
          <div className="flex items-center gap-6 text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-white transition-colors">
              How it works
            </a>
            <button
              onClick={() => {
                setActiveApiEndpoint(API_ENDPOINTS_CATALOG[0]);
                setApiModalOpen(true);
              }}
              className="hover:text-blue-400 transition-colors"
            >
              API Docs
            </button>
          </div>
          <div>© 2026 FinHelp. All rights reserved.</div>
        </div>
      </footer>

      {/* ========================================================================= */}
      {/* API INSPECTOR MODAL                                                       */}
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
