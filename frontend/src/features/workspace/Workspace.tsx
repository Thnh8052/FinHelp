import React, { useEffect, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Navbar } from "../../components/layout/Navbar";
import { SplitLayout } from "../../components/layout/SplitLayout";
import { DocumentManager } from "../../components/notebook/DocumentManager";
import { SourceViewer } from "../../components/notebook/SourceViewer";
import { ChatContainer } from "../../components/chat/ChatContainer";
import { ChatHistoryList } from "../../components/chat/ChatHistoryList";
import { StartScreen } from "../../components/chat/StartScreen";
import { AuthModal } from "../../components/auth/AuthModal";
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

  // Trích dẫn, form và trình đọc PDF đang mở thuộc về đoạn chat cũ
  useEffect(() => {
    setActiveCitation(null);
    setCatalogDocId(null);
    setIsSplitViewOpen(false);
  }, [notebookId]);

  // The chat needs about 480px beside the sidebar (232) and a panel (320 or 448): under 1480px only one panel fits, so opening one closes the other
  const oneAtATime = () => window.matchMedia("(max-width: 1480px)").matches;
  const openPdfPane = () => {
    setIsSplitViewOpen(true);
    if (oneAtATime()) setIsSourcesOpen(false);
    // sidebar 232 + source preview 448 leave a chat narrower than ~620px below 1320px (a table in an answer gets cut): the sidebar steps aside, one click brings it back
    if (window.matchMedia("(max-width: 1320px)").matches) setIsSidebarOpen(false);
  };
  const setSourcesOpen = (open: boolean) => {
    setIsSourcesOpen(open);
    if (open && oneAtATime()) setIsSplitViewOpen(false);
  };
  // "Document library" has no page of its own: it opens the drawer where the reports are managed (on a phone the sidebar drawer gives way)
  const openLibrary = () => {
    setSourcesOpen(true);
    if (window.matchMedia("(max-width: 768px)").matches) setIsSidebarOpen(false);
  };

  const unconfirmedDocs = docs.documents.filter(needsCatalogConfirmation);
  const notebookList = notebooks.map((n) => (n.notebook_id === notebookId ? { ...n, document_count: docs.documents.length, processing_count: docs.documents.filter(isDocProcessing).length } : n));

  // Khi click vào trích dẫn [1] Trang 12: Tự động mở Split-View, chuyển đúng tài liệu và nhảy tới trang đó
  const handleSelectCitation = (citation: CitationItem) => {
    setActiveCitation(citation);
    if (citation.document_id) {
      docs.setActiveDocId(citation.document_id);
    }
    openPdfPane();
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

      {/* Workstation: Sidebar | (top bar over Chat | Sources drawer | Source preview) */}
      <SplitLayout
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        header={
          <Navbar
            notebookTitle={notebookTitle}
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
            onOpenAuthModal={() => setAuthModalOpen(true)}
          />
        }
        sidebar={
          <ChatHistoryList
            notebooks={notebookList}
            activeNotebookId={notebookId}
            onSelectNotebook={selectNotebook}
            onNewChat={newChat}
            onRenameNotebook={renameNotebook}
            onDeleteNotebook={deleteNotebook}
            onNavigateHome={onNavigateHome}
            onOpenLibrary={openLibrary}
            onOpenAuth={() => setAuthModalOpen(true)}
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
              onFlagAnswer={chat.flagAnswer}
              hasOlder={chat.hasOlder}
              isLoadingOlder={chat.loadingOlder}
              onLoadOlder={chat.loadOlder}
              isLoading={chat.isLoading}
              loadingStage={chat.stage}
              onSelectCitation={handleSelectCitation}
              onToggleSources={() => setSourcesOpen(!isSourcesOpen)}
              isSourcesOpen={isSourcesOpen}
              documentNames={Object.fromEntries(docs.documents.map((d) => [d.document_id, d.file_name]))}
              chatKey={notebookId}
              startScreen={(pickQuestion) => (
                <StartScreen
                  documents={docs.documents}
                  isUploading={docs.isUploading}
                  isGuest={!isAuthenticated}
                  maxSources={maxSources}
                  maxFileSizeMb={maxFileSizeMb}
                  onUploadFiles={docs.uploadFiles}
                  onManage={() => setSourcesOpen(!isSourcesOpen)}
                  onPickQuestion={pickQuestion}
                />
              )}
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
              openPdfPane();
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
    </div>
  );
};

export default Workspace;

