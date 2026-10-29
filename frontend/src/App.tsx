import React, { useState } from "react";
import { Navbar } from "./components/layout/Navbar";
import { SplitLayout } from "./components/layout/SplitLayout";
import { DocumentManager } from "./components/notebook/DocumentManager";
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

  // Trạng thái điều khiển các Panel (Mockup V3)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);
  const [isSplitViewOpen, setIsSplitViewOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);

  // Mẫu xác nhận / sửa thông tin tài liệu (catalog) đang mở cho tài liệu nào
  const [catalogDocId, setCatalogDocId] = useState<string | null>(null);

  const { toast, showToast, closeToast, notebookTitle, isAuthenticated, docs, chat } = useWorkspace(() => setAuthModalOpen(true));

  const unconfirmedDocs = docs.documents.filter(needsCatalogConfirmation);
  const activeSession = chat.sessions.find((s) => s.session_id === chat.currentSessionId);
  const activeSessionTitle = activeSession?.title || (isAuthenticated ? "Hội thoại tài chính" : "Phiên dùng thử (Khách)");

  // Khi click vào trích dẫn [1] Trang 12: Tự động mở Split-View, chuyển đúng tài liệu và nhảy tới trang đó
  const handleSelectCitation = (citation: CitationItem) => {
    setActiveCitation(citation);
    if (citation.document_id) {
      docs.setActiveDocId(citation.document_id);
    }
    setIsSplitViewOpen(true);
  };

  return (
    <div className="app-container">
      {/* Modal chỉnh sửa thông tin BCTC (Catalog) */}
      <CatalogForm
        documentId={catalogDocId}
        onClose={() => setCatalogDocId(null)}
        onSaved={() => {
          showToast("Đã lưu thông tin tài liệu.", "success");
          docs.reload();
        }}
      />

      {/* Top-Center Toast Notification */}
      <Toast toast={toast} onClose={closeToast} />

      {/* Top Minimalist Header với 2 nút Toggle (Mockup V3) */}
      <Navbar
        notebookTitle={notebookTitle}
        sourcesCount={docs.documents.length}
        isSourcesOpen={isSourcesOpen}
        onToggleSources={() => setIsSourcesOpen((prev) => !prev)}
        isSplitViewOpen={isSplitViewOpen}
        onToggleSplitView={() => setIsSplitViewOpen((prev) => !prev)}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        onExportReport={() => showToast("Báo cáo phân tích đã được lưu.", "success")}
        onOpenAuthModal={() => setAuthModalOpen(true)}
        onOpenAdminDashboard={() => setAdminDashboardOpen(true)}
      />

      {/* Main 4-Zone Workstation (Sidebar | Chat | Sources Drawer | PDF Split-View) */}
      <SplitLayout
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
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
            {/* Banner yêu cầu xác nhận công ty/kỳ báo cáo nếu có */}
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
              onOpenSources={() => setIsSourcesOpen((prev) => !prev)}
              onToggleSources={() => setIsSourcesOpen((prev) => !prev)}
              isSourcesOpen={isSourcesOpen}
              hasSources={docs.selectedDocIds.length > 0}
              mentionOptions={docs.documents
                .filter((d) => docs.selectedDocIds.includes(d.document_id))
                .map((d) => ({ document_id: d.document_id, label: documentLabel(d) }))}
            />
          </div>
        }
        sourcesPane={
          <DocumentManager
            documents={docs.documents}
            activeDocId={docs.activeDocId}
            selectedDocIds={docs.selectedDocIds}
            onSelectDoc={docs.setActiveDocId}
            onToggleDoc={docs.toggleSelected}
            onToggleAllDocs={docs.toggleAll}
            onOpenDocPdf={(doc) => {
              docs.setActiveDocId(doc.document_id);
              setIsSplitViewOpen(true);
            }}
            onUploadFiles={docs.uploadFiles}
            onDeleteDocument={docs.remove}
            onEditCatalog={(docId) => setCatalogDocId(docId)}
            onClose={() => setIsSourcesOpen(false)}
            isUploading={docs.isUploading}
            isDeleting={docs.isDeleting}
          />
        }
        isSourcesOpen={isSourcesOpen}
        pdfViewerPane={
          <SourceViewer
            documents={docs.documents}
            activeDocId={docs.activeDocId}
            onSelectDoc={docs.setActiveDocId}
            activeCitation={activeCitation}
            onClearCitation={() => setActiveCitation(null)}
            onClose={() => setIsSplitViewOpen(false)}
          />
        }
        isSplitViewOpen={isSplitViewOpen}
      />

      {/* Auth Modal (Đăng nhập / Đăng ký / Quên mật khẩu) */}
      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />

      {/* Admin Dashboard Modal */}
      <AdminDashboardModal isOpen={adminDashboardOpen} onClose={() => setAdminDashboardOpen(false)} />
    </div>
  );
};

export default App;
