import React, { useState } from "react";
import { Navbar } from "./components/layout/Navbar";
import { SplitLayout } from "./components/layout/SplitLayout";
import { DocumentContextBar } from "./components/notebook/DocumentContextBar";
import { SourceViewer } from "./components/notebook/SourceViewer";
import { ChatContainer } from "./components/chat/ChatContainer";
import { ChatHistoryList } from "./components/chat/ChatHistoryList";
import { AuthModal } from "./components/auth/AuthModal";
import { AdminDashboardModal } from "./components/auth/AdminDashboardModal";
import { Toast } from "./components/common/Toast";
import { useWorkspace } from "./hooks/useWorkspace";
import { CitationItem } from "./types/chat";
import { documentLabel, needsCatalogConfirmation } from "./types/notebook";
import { CatalogForm } from "./components/notebook/CatalogForm";
import "./App.css";

export const App: React.FC = () => {
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [adminDashboardOpen, setAdminDashboardOpen] = useState(false);
  // Panel đối chiếu trích dẫn nguồn bên phải (Evidence Viewer)
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);
  // Mẫu xác nhận / sửa thông tin tài liệu (catalog) đang mở cho tài liệu nào
  const [catalogDocId, setCatalogDocId] = useState<string | null>(null);

  const { toast, showToast, closeToast, notebookTitle, isAuthenticated, docs, chat } = useWorkspace(() => setAuthModalOpen(true));

  const unconfirmedDocs = docs.documents.filter(needsCatalogConfirmation);
  const activeSession = chat.sessions.find((s) => s.session_id === chat.currentSessionId);
  const activeSessionTitle = activeSession?.title || (isAuthenticated ? "Hội thoại tài chính" : "Phiên dùng thử (Khách)");

  const handleSelectCitation = (citation: CitationItem) => {
    setActiveCitation(citation);
    setIsEvidenceOpen(true);
  };

  return (
    <div className="app-container">
      <CatalogForm
        documentId={catalogDocId}
        onClose={() => setCatalogDocId(null)}
        onSaved={() => {
          showToast("Đã lưu thông tin tài liệu.", "success");
          docs.reload();
        }}
      />

      {/* Top-Center Toast Notification (Không dùng Pop-up Confirm) */}
      <Toast toast={toast} onClose={closeToast} />

      {/* Top Minimalist Header */}
      <Navbar
        notebookTitle={notebookTitle}
        onExportReport={() => showToast("Báo cáo phân tích đã được lưu.", "success")}
        onOpenAuthModal={() => setAuthModalOpen(true)}
        onOpenAdminDashboard={() => setAdminDashboardOpen(true)}
      />

      {/* Main 3-Zone Financial Workstation */}
      <SplitLayout
        sidebar={
          <ChatHistoryList
            sessions={chat.sessions}
            activeSessionId={chat.currentSessionId}
            onSelectSession={chat.selectSession}
            onNewChat={chat.newChat}
            onDeleteSession={chat.deleteSession}
            isGuest={!isAuthenticated}
          />
        }
        main={
          <div className="main-workspace-flow">
            {/* Thanh tài liệu BCTC đang phân tích (Document Context Bar) */}
            <DocumentContextBar
              document={docs.activeDoc}
              documents={docs.documents}
              onSelectDoc={docs.setActiveDocId}
              selectedIds={docs.selectedDocIds}
              onToggleDoc={docs.toggleSelected}
              onUpload={docs.upload}
              onDeleteDocument={docs.remove}
              isUploading={docs.isUploading}
              isDeleting={docs.isDeleting}
              isAnalyzing={chat.isLoading}
              isEvidenceOpen={isEvidenceOpen}
              onToggleEvidence={() => setIsEvidenceOpen(!isEvidenceOpen)}
              hasActiveCitation={!!activeCitation}
              onEditCatalog={(docId) => setCatalogDocId(docId)}
            />

            {/* Tài liệu chưa xác minh được công ty / kỳ: phải xác nhận trước khi hỏi (backend cũng chặn) */}
            {unconfirmedDocs.length > 0 && (
              <div className="catalog-confirm-banner" role="status">
                <span>
                  Cần xác nhận thông tin tài liệu trước khi hỏi:{" "}
                  {unconfirmedDocs.map((d) => d.file_name).join(", ")}
                </span>
                <button type="button" onClick={() => setCatalogDocId(unconfirmedDocs[0].document_id)}>
                  Xác nhận
                </button>
              </div>
            )}

            {/* Khung Chat phân tích tài chính */}
            <ChatContainer
              messages={chat.messages}
              onSendMessage={chat.sendMessage}
              isLoading={chat.isLoading}
              onSelectCitation={handleSelectCitation}
              onClearChat={() => chat.setMessages([])}
              sessionTitle={activeSessionTitle}
              onNewChat={chat.newChat}
              hasSources={docs.selectedDocIds.length > 0}
              mentionOptions={docs.documents
                .filter((d) => docs.selectedDocIds.includes(d.document_id))
                .map((d) => ({ document_id: d.document_id, label: documentLabel(d) }))}
            />
          </div>
        }
        evidencePane={
          <SourceViewer
            activeCitation={activeCitation}
            onClearCitation={() => {
              setActiveCitation(null);
              setIsEvidenceOpen(false);
            }}
            documentName={docs.activeDoc?.file_name}
          />
        }
        isEvidenceOpen={isEvidenceOpen}
      />

      {/* Auth Modal (Đăng nhập / Đăng ký / Quên mật khẩu) */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />

      {/* Admin Dashboard Modal */}
      <AdminDashboardModal isOpen={adminDashboardOpen} onClose={() => setAdminDashboardOpen(false)} />
    </div>
  );
};

export default App;
