import React from "react";
import { FinHelpLogo } from "../../components/common/FinHelpLogo";

export interface ApiEndpointInfo {
  method: "POST" | "GET" | "PATCH" | "DELETE";
  path: string;
  title: string;
  feature: string;
  summary: string;
  payload?: string;
  response?: string;
}

export const API_ENDPOINTS_CATALOG: ApiEndpointInfo[] = [
  {
    method: "POST",
    path: "/api/v1/chat/query",
    feature: "AI-powered Q&A & So sánh đa tài liệu",
    title: "Gửi câu hỏi phân tích BCTC",
    summary:
      "Tiếp nhận câu hỏi ngôn ngữ tự nhiên từ người dùng, đối chiếu phạm vi tài liệu (1 hoặc nhiều BCTC), truy xuất các đoạn/bảng chính xác và sinh câu trả lời có trích dẫn minh bạch.",
    payload: JSON.stringify(
      {
        session_id: "sess_673fa1...",
        notebook_id: "nb_98a12...",
        query: "So sánh tăng trưởng doanh thu giữa 2 công ty...",
        scope_type: "explicit",
        document_ids: ["doc_comp_a", "doc_comp_b"],
      },
      null,
      2
    ),
    response: JSON.stringify(
      {
        answer: "Company A ghi nhận tăng trưởng doanh thu cao hơn...",
        citations: [
          { citation_num: 1, document_id: "doc_comp_a", page_number: 45, snippet: "Net revenue $17,902M..." },
          { citation_num: 2, document_id: "doc_comp_b", page_number: 32, snippet: "Net sales $30,120M..." },
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
    path: "/api/v1/documents/upload",
    feature: "Tải lên tài liệu BCTC",
    title: "Tải file PDF báo cáo tài chính",
    summary:
      "Tải file BCTC dạng PDF lên hệ thống. Bộ xử lý Docling tự động phân tích cấu trúc, nhận diện bảng biểu, trích xuất text và băm chunk có metadata ngữ cảnh.",
    payload: "Multipart/form-data: { file: File (PDF), notebook_id: string }",
    response: JSON.stringify(
      {
        document_id: "doc_comp_a_2023",
        file_name: "Company_A_Report_2023.pdf",
        status: "parsed",
        pages_count: 120,
        chunks_count: 342,
        tables_detected: 28,
      },
      null,
      2
    ),
  },
  {
    method: "GET",
    path: "/api/v1/documents/{id}/raw",
    feature: "Minh bạch trích dẫn (Evidence Viewer)",
    title: "Xem file PDF gốc và đối chiếu trang",
    summary:
      "Truy xuất file PDF gốc hoặc trang tài liệu tương ứng để người dùng kiểm chứng ngay trên trình xem PDF Split-View.",
    payload: "GET /api/v1/documents/doc_comp_a/raw",
    response: "Binary PDF stream (application/pdf)",
  },
  {
    method: "PATCH",
    path: "/api/v1/documents/{id}/catalog",
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
    path: "/api/v1/notebooks",
    feature: "Quản lý Không gian làm việc",
    title: "Lấy danh sách Notebook tài chính",
    summary: "Liệt kê các workspace phân tích của người dùng, phân tách tài liệu độc lập giữa các dự án nghiên cứu.",
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
    path: "/api/v1/chat/sessions",
    feature: "Lịch sử hội thoại (Conversation History)",
    title: "Lấy danh sách phiên phân tích đã lưu",
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
  const [selectedEndpoint, setSelectedEndpoint] = React.useState<ApiEndpointInfo>(
    activeEndpoint || API_ENDPOINTS_CATALOG[0]
  );

  React.useEffect(() => {
    if (activeEndpoint) {
      setSelectedEndpoint(activeEndpoint);
    }
  }, [activeEndpoint]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#0f172a] border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden text-slate-200">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-3">
            <FinHelpLogo size="sm" showText={false} />
            <div>
              <h3 className="font-heading font-bold text-white text-base">Sơ đồ Kết nối API Backend — FinHelp</h3>
              <p className="text-xs text-slate-400">
                Chi tiết các endpoint xử lý dữ liệu thực tế tương ứng với giao diện người dùng
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white flex items-center justify-center text-sm transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Modal Body: Two columns */}
        <div className="grid grid-cols-1 md:grid-cols-12 flex-1 overflow-hidden">
          {/* Left Column: Endpoints List */}
          <div className="md:col-span-5 border-r border-slate-800 overflow-y-auto p-3 space-y-1.5 bg-slate-950/40">
            <div className="px-3 py-2 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
              Danh sách Endpoint ({API_ENDPOINTS_CATALOG.length})
            </div>
            {API_ENDPOINTS_CATALOG.map((ep) => {
              const isSelected = selectedEndpoint.path === ep.path && selectedEndpoint.method === ep.method;
              return (
                <button
                  key={`${ep.method}-${ep.path}`}
                  onClick={() => setSelectedEndpoint(ep)}
                  className={`w-full text-left p-3 rounded-xl border text-xs transition-all flex flex-col gap-1 ${
                    isSelected
                      ? "bg-blue-600/15 border-blue-500/50 text-white"
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

          {/* Right Column: Endpoint Detailed Payload & Response */}
          <div className="md:col-span-7 p-6 overflow-y-auto space-y-5 bg-[#0f172a]">
            <div>
              <div className="flex items-center gap-2 mb-2">
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
              <h4 className="text-base font-bold text-white">{selectedEndpoint.title}</h4>
              <p className="text-xs text-slate-400 mt-1 leading-relaxed">{selectedEndpoint.summary}</p>
            </div>

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

            {/* Response */}
            {selectedEndpoint.response && (
              <div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Dữ liệu phản hồi (Response Output):</span>
                  <span className="text-[10px] text-emerald-400">200 OK</span>
                </div>
                <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 overflow-x-auto max-h-48">
                  {selectedEndpoint.response}
                </pre>
              </div>
            )}

            {/* Action button */}
            <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-800">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
              >
                Đóng
              </button>
              <button
                onClick={() => {
                  onClose();
                  onEnterWorkspace();
                }}
                className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/30 flex items-center gap-1.5"
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

