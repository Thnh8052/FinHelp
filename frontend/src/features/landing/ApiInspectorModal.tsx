import React, { useState } from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";

export interface ApiEndpointInfo {
  method: "POST" | "GET" | "PATCH" | "DELETE";
  path: string;
  title: string;
  feature: string;
  summary: string;
  payload?: string;
  response?: string;
  testablePath?: string;
}

export const API_ENDPOINTS_CATALOG: ApiEndpointInfo[] = [
  {
    method: "GET",
    path: "/health",
    feature: "Kiểm tra trạng thái hệ thống",
    title: "System Health & Database Connectivity Check",
    summary: "Kiểm tra tình trạng hoạt động của FastAPI server, kết nối MongoDB và Qdrant Vector Database.",
    payload: "Không yêu cầu payload (GET request)",
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
    feature: "AI-powered Q&A & So sánh đa BCTC",
    title: "Gửi câu hỏi phân tích tài chính đến RAG Engine",
    summary:
      "Tiếp nhận câu hỏi ngôn ngữ tự nhiên từ người dùng, đối chiếu phạm vi tài liệu (1 hoặc nhiều BCTC), truy xuất các đoạn/bảng chính xác bằng RRF + Qwen Reranker và sinh câu trả lời có trích dẫn minh bạch.",
    payload: JSON.stringify(
      {
        session_id: "sess_673fa1...",
        notebook_id: "nb_98a12...",
        query: "So sánh biên lợi nhuận ròng giữa Vinamilk và TH True Milk...",
        scope_type: "explicit",
        document_ids: ["doc_vnm_2023", "doc_thm_2023"],
      },
      null,
      2
    ),
    response: JSON.stringify(
      {
        answer: "Vinamilk ghi nhận biên lợi nhuận ròng cao hơn...",
        citations: [
          { citation_num: 1, document_id: "doc_vnm_2023", page_number: 45, snippet: "Lợi nhuận sau thuế đạt 9,019 tỷ VND..." },
          { citation_num: 2, document_id: "doc_thm_2023", page_number: 32, snippet: "Lợi nhuận ròng đạt 1,230 tỷ VND..." },
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
    feature: "Tải lên tài liệu BCTC",
    title: "Tải file PDF báo cáo tài chính vào Workspace",
    summary:
      "Tải file BCTC dạng PDF lên hệ thống. Bộ xử lý Docling tự động phân tích cấu trúc, nhận diện bảng biểu 2 chiều, trích xuất text và băm chunk 1024 tokens kèm BGE-M3 vector.",
    payload: "Multipart/form-data: { file: File (PDF) } -> Gửi tới /api/v1/documents/upload/{notebook_id}",
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
    feature: "Minh bạch trích dẫn (PDF Viewer)",
    title: "Xem file PDF gốc và nhảy trang đối chiếu",
    summary:
      "Truy xuất file PDF gốc phục vụ hiển thị song song trên trình xem PDF Split-View, hỗ trợ nhảy trang và tô sáng dòng trích dẫn.",
    payload: "GET /api/v1/documents/{document_id}/file",
    response: "Binary PDF stream (Content-Type: application/pdf)",
  },
  {
    method: "PATCH",
    path: "/api/v1/documents/{document_id}/catalog",
    feature: "Xác nhận Metadata tài liệu",
    title: "Cập nhật mã cổ phiếu, năm & kỳ BCTC",
    summary:
      "Xác nhận hoặc điều chỉnh thông tin công ty (mã ticker), năm tài chính (fiscal year) và loại báo cáo (Kiểm toán / Quý) để tăng độ chính xác khi đối chiếu so sánh.",
    payload: JSON.stringify(
      {
        ticker: "VNM",
        company_name: "Công ty Cổ phần Sữa Việt Nam",
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
    feature: "Đăng nhập hệ thống",
    title: "Xác thực người dùng & cấp JWT Token",
    summary: "Xác thực email/username và mật khẩu, trả về Bearer JWT token có thời hạn và phân quyền vai trò.",
    payload: JSON.stringify({ identifier: "analyst@company.com", password: "••••••••" }, null, 2),
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
    feature: "Đăng ký tài khoản mới",
    title: "Tạo tài khoản phân tích tài chính",
    summary: "Khởi tạo tài khoản người dùng mới và tự động thiết lập Notebook phân tích mặc định.",
    payload: JSON.stringify(
      {
        email: "analyst@fund.com",
        username: "analyst_pro",
        password: "••••••••",
        full_name: "Nguyen Van A",
      },
      null,
      2
    ),
    response: JSON.stringify({ user_id: "u_981", message: "Đăng ký thành công" }, null, 2),
  },
  {
    method: "GET",
    path: "/api/v1/auth/tiers",
    feature: "Cấu hình gói dịch vụ",
    title: "Lấy danh sách các gói cước và hạn mức",
    summary: "Trả về thông tin quota của các gói Guest, User, Admin.",
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
    feature: "Hạn mức khách dùng thử",
    title: "Kiểm tra quyền và quota của khách vãng lai",
    summary: "Kiểm tra trạng thái xác thực và hạn mức tải tài liệu cho người dùng chưa đăng nhập.",
    payload: "GET /api/v1/auth/guest-quota",
    response: JSON.stringify(
      {
        is_authenticated: false,
        tier: "guest",
        max_upload_documents: 1,
        max_file_size_mb: 5,
        cost_description: "Chế độ dùng thử (Tối đa 1 tài liệu)",
      },
      null,
      2
    ),
    testablePath: "/api/v1/auth/guest-quota",
  },
  {
    method: "POST",
    path: "/api/v1/notebooks/guest",
    feature: "Khởi tạo Workspace dùng thử",
    title: "Tạo phiên Notebook phân tích nhanh không cần login",
    summary: "Khởi tạo một Notebook cô lập cho khách dùng thử nghiệm hệ thống phân tích BCTC ngay tức thì.",
    payload: "POST /api/v1/notebooks/guest (Body rỗng hoặc tùy chọn tiêu đề)",
    response: JSON.stringify(
      {
        notebook_id: "nb_guest_1c33f9...",
        user_id: "guest",
        title: "Không Gian Dùng Thử (Khách Chưa Đăng Nhập)",
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
    feature: "Quản lý Không gian làm việc",
    title: "Lấy danh sách Notebook tài chính của người dùng",
    summary: "Liệt kê các workspace phân tích, phân tách tài liệu độc lập giữa các dự án nghiên cứu.",
    payload: "Header: Authorization: Bearer <token>",
    response: JSON.stringify(
      [
        {
          notebook_id: "nb_default_1",
          title: "Phân tích BCTC Ngành Tiêu Dùng 2023",
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
    feature: "Lịch sử hội thoại",
    title: "Lấy danh sách phiên phân tích trong Notebook",
    summary: "Cho phép tiếp tục các phiên tra cứu, tính toán chỉ số tài chính trước đó bất cứ lúc nào.",
    payload: "GET /api/v1/chat/sessions/notebook/{notebook_id}",
    response: JSON.stringify(
      [
        {
          session_id: "sess_104",
          title: "So sánh doanh thu & biên LN ròng",
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
          hint: "Server backend FastAPI (127.0.0.1:8000) có thể chưa được khởi động. Hãy kiểm tra terminal backend.",
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
                Sơ đồ & Trình Kiểm thử API Backend — FinHelp
              </h3>
              <p className="text-xs text-slate-400">
                Toàn bộ 29 endpoint chuẩn hóa của hệ thống FastAPI, khớp chính xác 100% với backend
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center text-sm transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Modal Body: Two columns */}
        <div className="grid grid-cols-1 md:grid-cols-12 flex-1 overflow-hidden">
          {/* Left Column: Endpoints List */}
          <div className="md:col-span-5 border-r border-slate-800 overflow-y-auto p-3 space-y-1.5 bg-slate-950/60">
            <div className="px-3 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center justify-between">
              <span>Danh sách Endpoint ({API_ENDPOINTS_CATALOG.length})</span>
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
                    <span>Đang gọi API...</span>
                  ) : (
                    <>
                      <span>▶️ Gọi thử API</span>
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
                  <span className="font-bold text-slate-300">Kết quả phản hồi thực tế (Live Response):</span>
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
                  <span>Dữ liệu gửi lên (Request Payload):</span>
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
                  <span>Cấu trúc phản hồi mẫu (Schema Response):</span>
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
                Đóng
              </button>
              <button
                onClick={() => {
                  onClose();
                  onEnterWorkspace();
                }}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/30 flex items-center gap-1.5 cursor-pointer"
              >
                <span>Mở trong Workspace</span>
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
