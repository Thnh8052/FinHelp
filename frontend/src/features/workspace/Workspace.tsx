import React, { useEffect, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Navbar } from "../../components/layout/Navbar";
import { SplitLayout } from "../../components/layout/SplitLayout";
import { DocumentManager } from "../../components/notebook/DocumentManager";
import { SourceViewer } from "../../components/notebook/SourceViewer";
import { ChatContainer } from "../../components/chat/ChatContainer";
import { ChatHistoryList } from "../../components/chat/ChatHistoryList";
import { AuthModal } from "../../components/auth/AuthModal";
import { AdminDashboardModal } from "../../components/auth/AdminDashboardModal";
import { Toast } from "../../components/common/Toast";
import { useWorkspace } from "../../hooks/useWorkspace";
import { CitationItem } from "../../types/chat";
import { documentLabel, isDocProcessing, needsCatalogConfirmation } from "../../types/notebook";
import { CatalogForm } from "../../components/notebook/CatalogForm";

interface WorkspaceProps {
  onNavigateHome?: () => void;
  initialAuthModalOpen?: boolean;
}

export const Workspace: React.FC<WorkspaceProps> = ({
  onNavigateHome,
  initialAuthModalOpen = false,
}) => {
  const [authModalOpen, setAuthModalOpen] = useState(initialAuthModalOpen);
  const [adminDashboardOpen, setAdminDashboardOpen] = useState(false);

  // Panel control states (Desktop: open by default, Mobile: closed drawer)
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => typeof window !== "undefined" && window.innerWidth > 768);
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);
  const [isSplitViewOpen, setIsSplitViewOpen] = useState(false);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);

  // Catalog edit modal for documents
  const [catalogDocId, setCatalogDocId] = useState<string | null>(null);
  const { t } = useLanguage();

  const { toast, showToast, closeToast, notebookTitle, isAuthenticated, maxSources, maxFileSizeMb, docs, chat, notebooks, notebookId, selectNotebook, newChat, renameNotebook, deleteNotebook } = useWorkspace(
    () => setAuthModalOpen(true)
  );

  // Trích dẫn và form đang mở thuộc về đoạn chat cũ
  useEffect(() => {
    setActiveCitation(null);
    setCatalogDocId(null);
  }, [notebookId]);

  const unconfirmedDocs = docs.documents.filter(needsCatalogConfirmation);
  const notebookList = notebooks.map((n) => (n.notebook_id === notebookId ? { ...n, document_count: docs.documents.length, processing_count: docs.documents.filter(isDocProcessing).length } : n));
  const activeSessionTitle = notebookTitle || (isAuthenticated ? t.workspace.financialAnalysisSession : t.workspace.guestTrialSession);

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
          showToast(t.toasts.catalogSaved, "success");
          docs.reload();
        }}
      />

      {/* Trong lúc gửi tệp lên: chặn mọi thao tác, vì rời trang lúc này sẽ làm mất tệp đang gửi */}
      {docs.isUploading && (
        <div className="upload-lock-overlay" role="status" aria-live="polite">
          <span className="chat-processing-spinner" />
          <span>{t.workspace.uploadingNotice}</span>
        </div>
      )}

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
        onOpenAuthModal={() => setAuthModalOpen(true)}
        onOpenAdminDashboard={() => setAdminDashboardOpen(true)}
        onNavigateHome={onNavigateHome}
      />

      {/* Main 4-Zone Workstation (Sidebar | Chat | Sources Drawer | PDF Split-View) */}
      <SplitLayout
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        sidebar={
          <ChatHistoryList
            notebooks={notebookList}
            activeNotebookId={notebookId}
            onSelectNotebook={selectNotebook}
            onNewChat={newChat}
            onRenameNotebook={renameNotebook}
            onDeleteNotebook={deleteNotebook}
            isGuest={!isAuthenticated}
          />
        }
        main={
          <div className="main-workspace-flow">
            {/* Banner yêu cầu xác nhận công ty/kỳ báo cáo nếu có */}
            {unconfirmedDocs.length > 0 && (
              <div className="catalog-confirm-banner" role="status">
                <span>
                  {t.workspace.confirmMetadataNotice}{" "}
                  {unconfirmedDocs.map((d) => d.file_name).join(", ")}
                </span>
                <button type="button" onClick={() => setCatalogDocId(unconfirmedDocs[0].document_id)}>
                  {t.workspace.confirmBtn}
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
              onNewChat={newChat}
              onOpenSources={() => setIsSourcesOpen((prev) => !prev)}
              onToggleSources={() => setIsSourcesOpen((prev) => !prev)}
              isSourcesOpen={isSourcesOpen}
              hasSources={docs.selectedDocIds.length > 0}
              isProcessing={docs.isUploading || docs.documents.some(isDocProcessing)}
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
            maxSources={maxSources}
            maxFileSizeMb={maxFileSizeMb}
          />
        }
        isSourcesOpen={isSourcesOpen}
        pdfViewerPane={
          <SourceViewer
            documents={docs.documents.filter((d) => d.status === "ready")}
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

export default Workspace;

