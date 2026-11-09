import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../../context/LanguageContext";
import { AdminDashboardModal } from "../../components/auth/AdminDashboardModal";
import { AuthModal } from "../../components/auth/AuthModal";
import { PlusIcon } from "../../components/common/Icons";
import { Toast } from "../../components/common/Toast";
import { Navbar } from "../../components/layout/Navbar";
import { NotebookCard } from "./NotebookCard";
import { useNotebookHub } from "./useNotebookHub";
import "./hub.css";

const SEARCH_FROM = 3;
const SKELETON_CARDS = 6;

/** Trang đầu của người dùng đã đăng nhập: toàn bộ sổ tay (mỗi sổ tay là một đoạn chat). */
export const NotebookHub: React.FC<{ onNavigateHome: () => void }> = ({ onNavigateHome }) => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const hub = useNotebookHub();
  const [search, setSearch] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);

  const openNew = async () => {
    setIsCreating(true);
    const notebookId = await hub.create(t.hub.createFailed);
    setIsCreating(false);
    if (notebookId) navigate(`/app/${notebookId}`);
  };

  const newButton = (
    <button type="button" className="hub-new-btn" onClick={openNew} disabled={isCreating}>
      <PlusIcon size={15} />
      <span>{t.hub.newNotebook}</span>
    </button>
  );

  const term = search.trim().toLowerCase();
  const visible = hub.notebooks?.filter((n) => n.title.toLowerCase().includes(term)) ?? [];

  const content = () => {
    if (hub.loadFailed && !hub.notebooks) {
      return (
        <div className="hub-state" role="alert">
          <h2 className="hub-state-title">{t.hub.loadFailed}</h2>
          <button type="button" className="hub-text-btn" onClick={() => void hub.load()}>{t.common.retry}</button>
        </div>
      );
    }
    if (!hub.notebooks) {
      return (
        <ul className="hub-grid" aria-busy="true" aria-label={t.common.loading}>
          {Array.from({ length: SKELETON_CARDS }, (_, i) => <li key={i} className="hub-card hub-card-skeleton" />)}
        </ul>
      );
    }
    if (hub.notebooks.length === 0) {
      return (
        <div className="hub-state">
          <h2 className="hub-state-title">{t.hub.emptyTitle}</h2>
          <p className="hub-state-text">{t.hub.emptyText}</p>
          {newButton}
        </div>
      );
    }
    if (visible.length === 0) {
      return <div className="hub-state" role="status"><p className="hub-state-text">{t.hub.noMatch}</p></div>;
    }
    return (
      <ul className="hub-grid">
        {visible.map((notebook) => (
          <NotebookCard
            key={notebook.notebook_id}
            notebook={notebook}
            onRename={(id, title) => hub.rename(id, title, t.hub.renameFailed)}
            onDelete={(id) => hub.remove(id, t.hub.deleted, t.hub.deleteFailed)}
          />
        ))}
      </ul>
    );
  };

  return (
    <div className="app-container">
      <Toast toast={hub.toast} onClose={hub.closeToast} />
      <Navbar
        notebookTitle={t.hub.title}
        onOpenAuthModal={() => setAuthModalOpen(true)}
        onOpenAdminDashboard={() => setAdminOpen(true)}
        onNavigateHome={onNavigateHome}
      />

      <main className="hub-main">
        <div className="hub-inner">
          <header className="hub-header">
            <div>
              <h1 className="hub-title">{t.hub.title}</h1>
              <p className="hub-subtitle">{t.hub.subtitle}</p>
            </div>
            {newButton}
          </header>

          {(hub.notebooks?.length ?? 0) >= SEARCH_FROM && (
            <input
              type="search"
              className="hub-input hub-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.hub.search}
              aria-label={t.hub.search}
            />
          )}

          {content()}
        </div>
      </main>

      <AuthModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
      <AdminDashboardModal isOpen={adminOpen} onClose={() => setAdminOpen(false)} />
    </div>
  );
};

export default NotebookHub;
