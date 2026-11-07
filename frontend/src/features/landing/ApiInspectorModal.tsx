import React, { useState } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";

export interface ApiEndpointInfo {
  method: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  path: string;
  feature: string;
  title: string;
  summary: string;
  payload?: string;
  response?: string;
  testablePath?: string;
}

export const API_ENDPOINTS_CATALOG: ApiEndpointInfo[] = [
  {
    method: "GET",
    path: "/health",
    feature: "System Health & DB Connectivity",
    title: "System Health & Vector Database Check",
    summary: "Monitors the runtime health of the FastAPI application server, MongoDB connectivity, and Qdrant Vector Search engine.",
    payload: "No payload required (GET request)",
    response: JSON.stringify(
      {
        status: "healthy",
        project: "DATN Finance - Financial RAG System",
        version: "1.0.0",
        database: "mongodb_connected",
        vector_search: "qdrant_connected",
      },
      null,
      2
    ),
    testablePath: "/health",
  },
  {
    method: "POST",
    path: "/api/v1/chat/query",
    feature: "AI-Powered Q&A & Multi-Report",
    title: "Submit Financial Query to RAG Engine",
    summary:
      "Accepts natural language financial questions, determines document scopes (single or multi-filing), retrieves dense/sparse chunks via RRF + Qwen Reranker, and generates grounded answers with auditable citations.",
    payload: JSON.stringify(
      {
        session_id: "sess_673fa1...",
        notebook_id: "nb_98a12...",
        query: "Compare net profit margin between Vinamilk and TH True Milk for FY2023...",
        scope_type: "explicit",
        document_ids: ["doc_vnm_2023", "doc_thm_2023"],
      },
      null,
      2
    ),
    response: JSON.stringify(
      {
        answer: "Vinamilk reported a higher net profit margin of 14.9% compared to TH True Milk's 8.2%...",
        citations: [
          { citation_num: 1, document_id: "doc_vnm_2023", page_number: 45, snippet: "Net profit after tax reached 9,019 billion VND..." },
          { citation_num: 2, document_id: "doc_thm_2023", page_number: 32, snippet: "Net profit after tax reached 1,230 billion VND..." },
        ],
        confidence: 0.96,
        sources_used: 2,
      },
      null,
      2
    ),
  },
  {
    method: "POST",
    path: "/api/v1/documents/upload/{notebook_id}",
    feature: "Document Upload & Ingestion",
    title: "Upload PDF Financial Statement into Workspace",
    summary:
      "Uploads financial PDF files. Docling automatically parses document layout, extracts two-dimensional tables, extracts raw text, and generates 1024-token semantic chunks with BGE-M3 embeddings.",
    payload: "Multipart/form-data: { file: File (PDF) } -> Sent to /api/v1/documents/upload/{notebook_id}",
    response: JSON.stringify(
      {
        document_id: "doc_vnm_2023",
        file_name: "Vinamilk_Annual_Report_2023.pdf",
        status: "parsing",
        page_count: 120,
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/api/v1/documents/{document_id}/file",
    feature: "Source Grounding (PDF Viewer)",
    title: "Stream Original PDF & Jump to Citation Page",
    summary:
      "Streams the raw original PDF file for side-by-side verification in the split-view viewer, supporting direct page jumping and text highlight pulses.",
    payload: "GET /api/v1/documents/{document_id}/file",
    response: "Binary PDF stream (Content-Type: application/pdf)",
  },
  {
    method: "PATCH",
    path: "/api/v1/documents/{document_id}/catalog",
    feature: "Metadata Confirmation",
    title: "Update Ticker, Fiscal Year & Statement Period",
    summary:
      "Confirms or updates document metadata (stock ticker, fiscal year, report period, audit status) to ensure precision across multi-document comparative queries.",
    payload: JSON.stringify(
      {
        ticker: "VNM",
        company_name: "Vietnam Dairy Products Joint Stock Company",
        fiscal_year: 2023,
        report_period: "FY",
        is_audited: true,
      },
      null,
      2
    ),
    response: JSON.stringify({ success: true, document_id: "doc_123", status: "confirmed" }, null, 2),
  },
  {
    method: "POST",
    path: "/api/v1/auth/login-json",
    feature: "User Authentication",
    title: "Authenticate User & Issue JWT Token",
    summary: "Authenticates email/username and password, returning a signed Bearer JWT token with role-based access control.",
    payload: JSON.stringify({ identifier: "analyst@fund.com", password: "••••••••" }, null, 2),
    response: JSON.stringify(
      {
        access_token: "eyJhbGciOi...",
        token_type: "bearer",
        role: "user",
        tier: "pro",
      },
      null,
      2
    ),
  },
  {
    method: "POST",
    path: "/api/v1/auth/register",
    feature: "User Registration",
    title: "Create New Financial Analyst Account",
    summary: "Initializes a new user account and automatically provisions a default analysis notebook workspace.",
    payload: JSON.stringify(
      {
        email: "analyst@fund.com",
        username: "analyst_pro",
        password: "••••••••",
        full_name: "Alex Morgan",
      },
      null,
      2
    ),
    response: JSON.stringify({ user_id: "u_981", message: "Registration successful" }, null, 2),
  },
  {
    method: "GET",
    path: "/api/v1/auth/tiers",
    feature: "Tier & Quota Configuration",
    title: "Get Subscription Plans and Usage Quotas",
    summary: "Returns usage quota limits for Guest, User, and Admin access tiers.",
    payload: "GET /api/v1/auth/tiers",
    response: JSON.stringify(
      {
        tiers: {
          guest: { max_upload_documents: 1, max_file_size_mb: 5 },
          user: { max_upload_documents: 5, max_file_size_mb: 20 },
          admin: { max_upload_documents: 50, max_file_size_mb: 100 },
        },
      },
      null,
      2
    ),
    testablePath: "/api/v1/auth/tiers",
  },
  {
    method: "GET",
    path: "/api/v1/auth/guest-quota",
    feature: "Guest Quota Verification",
    title: "Check Current Guest Privileges & Limits",
    summary: "Checks authentication status and document upload quota for unauthenticated visitors.",
    payload: "GET /api/v1/auth/guest-quota",
    response: JSON.stringify(
      {
        is_authenticated: false,
        tier: "guest",
        max_upload_documents: 1,
        max_file_size_mb: 5,
        cost_description: "Guest trial mode (Maximum 1 document)",
      },
      null,
      2
    ),
    testablePath: "/api/v1/auth/guest-quota",
  },
  {
    method: "POST",
    path: "/api/v1/notebooks/guest",
    feature: "Guest Workspace Setup",
    title: "Initialize Isolated Trial Notebook (No Login Needed)",
    summary: "Instantly provisions an isolated workspace notebook allowing visitors to test financial RAG analysis immediately.",
    payload: "POST /api/v1/notebooks/guest (Empty body or optional title)",
    response: JSON.stringify(
      {
        notebook_id: "nb_guest_1c33f9...",
        user_id: "guest",
        title: "Guest Analysis Workspace",
        document_ids: [],
      },
      null,
      2
    ),
    testablePath: "/api/v1/notebooks/guest",
  },
  {
    method: "GET",
    path: "/api/v1/notebooks",
    feature: "Workspace Management",
    title: "List User Financial Analysis Notebooks",
    summary: "Lists all workspace notebooks, providing isolated document collections across different research projects.",
    payload: "Header: Authorization: Bearer <token>",
    response: JSON.stringify(
      [
        {
          notebook_id: "nb_default_1",
          title: "Consumer Goods Sector Analysis FY2023",
          documents_count: 5,
          created_at: "2026-11-01T08:00:00Z",
        },
      ],
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/api/v1/chat/sessions/notebook/{notebook_id}",
    feature: "Conversation History",
    title: "List Analysis Sessions in Notebook",
    summary: "Enables resumption of previous Q&A threads, ratio analyses, and calculations at any time.",
    payload: "GET /api/v1/chat/sessions/notebook/{notebook_id}",
    response: JSON.stringify(
      [
        {
          session_id: "sess_104",
          title: "Revenue & Operating Margin Comparison",
          messages_count: 8,
          updated_at: "2026-11-07T12:30:00Z",
        },
      ],
      null,
      2
    ),
  },
];

interface ApiInspectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeEndpoint?: ApiEndpointInfo | null;
  onEnterWorkspace: () => void;
}

export const ApiInspectorModal: React.FC<ApiInspectorModalProps> = ({
  isOpen,
  onClose,
  activeEndpoint,
  onEnterWorkspace,
}) => {
  const [selectedEndpoint, setSelectedEndpoint] = useState<ApiEndpointInfo>(
    activeEndpoint || API_ENDPOINTS_CATALOG[0]
  );
  const [liveTestLoading, setLiveTestLoading] = useState(false);
  const [liveTestResult, setLiveTestResult] = useState<{ status: number | string; time: number; data: any } | null>(null);

  React.useEffect(() => {
    if (activeEndpoint) {
      setSelectedEndpoint(activeEndpoint);
      setLiveTestResult(null);
    }
  }, [activeEndpoint]);

  if (!isOpen) return null;

  const handleTestLiveEndpoint = async (ep: ApiEndpointInfo) => {
    setLiveTestLoading(true);
    setLiveTestResult(null);
    const start = performance.now();
    try {
      const targetUrl = ep.testablePath || ep.path;
      const res = await fetch(targetUrl, {
        method: ep.method,
        headers: { "Content-Type": "application/json" },
      });
      const elapsed = Math.round(performance.now() - start);
      let data: any;
      try {
        data = await res.json();
      } catch {
        data = await res.text();
      }
      setLiveTestResult({ status: res.status, time: elapsed, data });
    } catch (err: any) {
      const elapsed = Math.round(performance.now() - start);
      setLiveTestResult({
        status: "Connection Failed",
        time: elapsed,
        data: {
          error: err.message,
          hint: "FastAPI backend server (127.0.0.1:8000) may not be running. Please check your backend process.",
        },
      });
    } finally {
      setLiveTestLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/85 backdrop-blur-md animate-fade-in">
      <div className="bg-[#0f172a] border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden text-slate-200">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <FinHelpLogo size="sm" showText={false} />
            <div>
              <h3 className="font-heading font-bold text-white text-base">
                Backend API Inspector & Live Tester — FinHelp
              </h3>
              <p className="text-xs text-slate-400">
                Complete catalog of 29 normalized FastAPI endpoints matching backend specifications
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center text-sm transition-colors cursor-pointer"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Modal Body: Two columns */}
        <div className="grid grid-cols-1 md:grid-cols-12 flex-1 overflow-hidden">
          {/* Left Column: Endpoints List */}
          <div className="md:col-span-5 border-r border-slate-800 overflow-y-auto p-3 space-y-1.5 bg-slate-950/60">
            <div className="px-3 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Endpoints List ({API_ENDPOINTS_CATALOG.length})</span>
              <span className="text-emerald-400 font-mono text-[10px]">OpenAPI 3.1</span>
            </div>
            {API_ENDPOINTS_CATALOG.map((ep) => {
              const isSelected = selectedEndpoint.path === ep.path && selectedEndpoint.method === ep.method;
              return (
                <button
                  key={`${ep.method}-${ep.path}`}
                  onClick={() => {
                    setSelectedEndpoint(ep);
                    setLiveTestResult(null);
                  }}
                  className={`w-full text-left p-3 rounded-xl border text-xs transition-all flex flex-col gap-1 cursor-pointer ${
                    isSelected
                      ? "bg-blue-600/20 border-blue-500/60 text-white shadow-sm"
                      : "bg-slate-900/60 border-slate-800/80 text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                        ep.method === "POST"
                          ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                          : ep.method === "GET"
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {ep.method}
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium">{ep.feature}</span>
                  </div>
                  <div className="font-mono text-[11px] text-slate-300 truncate">{ep.path}</div>
                  <div className="text-[11px] text-slate-400 line-clamp-1">{ep.title}</div>
                </button>
              );
            })}
          </div>

          {/* Right Column: Endpoint Detailed Payload & Live Tester */}
          <div className="md:col-span-7 p-6 overflow-y-auto space-y-5 bg-[#0f172a]">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                      selectedEndpoint.method === "POST"
                        ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                        : selectedEndpoint.method === "GET"
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    }`}
                  >
                    {selectedEndpoint.method}
                  </span>
                  <span className="font-mono text-sm font-semibold text-white">{selectedEndpoint.path}</span>
                </div>

                {/* Live Test Button */}
                <button
                  onClick={() => handleTestLiveEndpoint(selectedEndpoint)}
                  disabled={liveTestLoading}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/40 text-xs font-mono font-semibold flex items-center gap-1.5 cursor-pointer transition-colors"
                >
                  {liveTestLoading ? (
                    <span>Testing Endpoint...</span>
                  ) : (
                    <>
                      <span>▶️ Run Live Test</span>
                    </>
                  )}
                </button>
              </div>
              <h4 className="text-base font-bold text-white">{selectedEndpoint.title}</h4>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">{selectedEndpoint.summary}</p>
            </div>

            {/* Live Test Output if present */}
            {liveTestResult && (
              <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-700 space-y-2 animate-fade-in">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-300">Live Response Output:</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                        liveTestResult.status === 200
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      Status: {liveTestResult.status}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">{liveTestResult.time}ms</span>
                  </div>
                </div>
                <pre className="p-2.5 rounded bg-slate-900 text-xs font-mono text-slate-300 overflow-x-auto max-h-36">
                  {JSON.stringify(liveTestResult.data, null, 2)}
                </pre>
              </div>
            )}

            {/* Request Payload */}
            {selectedEndpoint.payload && (
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Request Payload:</span>
                  <span className="text-[10px] text-slate-500">JSON / Form</span>
                </div>
                <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto">
                  {selectedEndpoint.payload}
                </pre>
              </div>
            )}

            {/* Expected Response */}
            {selectedEndpoint.response && (
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Schema Response:</span>
                  <span className="text-[10px] text-emerald-400">200 OK</span>
                </div>
                <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto max-h-44">
                  {selectedEndpoint.response}
                </pre>
              </div>
            )}

            {/* Footer Action buttons */}
            <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-800">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium cursor-pointer"
              >
                Close
              </button>
              <button
                onClick={() => {
                  onClose();
                  onEnterWorkspace();
                }}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/30 flex items-center gap-1.5 cursor-pointer"
              >
                <span>Open in Workspace</span>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ApiInspectorModal;
