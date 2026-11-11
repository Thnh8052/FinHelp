import React, { useRef, useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Notebook } from "../../types/notebook";
import { CheckIcon, CloseIcon, MessageSquareIcon, PencilIcon, PlusIcon, TrashIcon } from "../common/Icons";
import "./chat.css";

interface ChatHistoryListProps {
  notebooks: Notebook[];
  activeNotebookId: string | null;
  onSelectNotebook: (notebookId: string) => void;
  onNewChat: () => void;
  onRenameNotebook: (notebookId: string, title: string) => Promise<boolean>;
  onDeleteNotebook: (notebookId: string) => void;
  isGuest?: boolean;
}

/**
 * Danh sách đoạn chat (mỗi notebook là một đoạn chat)
 * Provides "New Analysis" button, session cards with metadata, and secure workspace footer.
 */
export const ChatHistoryList: React.FC<ChatHistoryListProps> = ({
  notebooks,
  activeNotebookId,
  onSelectNotebook,
  onNewChat,
  onRenameNotebook,
  onDeleteNotebook,
  isGuest = false,
}) => {
  const { t } = useLanguage();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const cancelled = useRef(false);  // Escape unmounts the input, which some browsers report as a blur: that must not save

  const saveRename = async (session: Notebook) => {
    const title = draft.trim();
    const id = session.notebook_id;
    setRenamingId(null);  // an empty or unchanged name keeps the old one
    if (cancelled.current) return;
    if (title && title !== session.title) await onRenameNotebook(id, title);
  };

  const filteredNotebooks = notebooks.filter((s) =>
    (s.title || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="history-container">
      {/* 1. New Chat Action */}
      <div className="history-top-section">
        <button
          type="button"
          onClick={onNewChat}
          className="history-new-btn group"
          title={t.sidebar.newSessionTitle}
        >
          <div className="history-new-btn-left">
            <PlusIcon size={16} className="history-plus-icon" />
            <span>{t.sidebar.newAnalysis}</span>
          </div>
          <span className="history-new-tag">
            {isGuest ? t.sidebar.badgeLogin : t.sidebar.badgeNew}
          </span>
        </button>
      </div>

      {/* 2. Section Header */}
      <div className="history-section-header">
        <span className="history-section-title">{t.sidebar.historyTitle}</span>
        <span className="history-section-count">{notebooks.length} {t.sidebar.sessionsCount}</span>
      </div>

      {/* Search Filter */}
      {notebooks.length >= 3 && (
        <div className="history-search-box">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={t.sidebar.searchPlaceholder}
            className="history-search-input"
          />
        </div>
      )}

      {/* Guest Mode Banner */}
      {isGuest && (
        <div className="history-guest-banner">
          <div className="history-guest-badge">{t.sidebar.guestBannerTitle}</div>
          <div>{t.sidebar.guestBannerDesc}</div>
        </div>
      )}

      {/* 3. Session Cards List */}
      <div className="history-list scrollbar-slim">
        {filteredNotebooks.length === 0 ? (
          <div className="history-empty">
            {searchTerm
              ? t.sidebar.noSessionsMatch
              : t.sidebar.noSessionsYet}
          </div>
        ) : (
          filteredNotebooks.map((session) => {
            const isActive = session.notebook_id === activeNotebookId;
            const isHovered = hoveredId === session.notebook_id;

            return (
              <div
                key={session.notebook_id}
                onClick={() => onSelectNotebook(session.notebook_id)}
                onMouseEnter={() => setHoveredId(session.notebook_id)}
                onMouseLeave={() => setHoveredId(null)}
                className={`history-card ${isActive ? "active" : ""}`}
              >
                <div className="history-card-inner">
                  <div className="history-card-main">
                    <MessageSquareIcon
                      size={15}
                      color={isActive ? "#60a5fa" : "#64748b"}
                      className="history-card-icon"
                    />
                    <div className="history-card-info">
                      {renamingId === session.notebook_id ? (
                        <input
                          className="history-rename-input"
                          value={draft}
                          maxLength={120}
                          autoFocus
                          aria-label={t.hub.renameLabel}
                          onClick={(e) => e.stopPropagation()}
                          onFocus={(e) => e.target.select()}
                          onChange={(e) => setDraft(e.target.value)}
                          onBlur={() => void saveRename(session)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") e.currentTarget.blur();
                            if (e.key === "Escape") {
                              cancelled.current = true;
                              setRenamingId(null);
                            }
                          }}
                        />
                      ) : (
                        <p
                          className="history-card-title"
                          title={session.title || t.sidebar.untitledSession}
                        >
                          {session.title || t.sidebar.untitledSession}
                        </p>
                      )}
                      <p className="history-card-sub">
                        <span>{((session.document_count ?? 0) === 1 ? t.hub.fileOne : t.hub.fileMany).replace("{n}", String(session.document_count ?? 0))}</span>
                        <span>•</span>
                        {(session.processing_count ?? 0) > 0 ? (
                          <span className="history-card-processing">
                            <span className="chat-processing-spinner" aria-hidden="true" />
                            {t.hub.processing}
                          </span>
                        ) : (
                          <span className={isActive ? "status-active" : "status-saved"}>
                            {isActive ? t.sidebar.statusActive : t.sidebar.statusSaved}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Delete: removes the chat with all its files, so it asks first */}
                  {confirmingId === session.notebook_id ? (
                    <div className="history-card-confirm" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        aria-label={`${t.common.delete}: ${session.title || t.sidebar.untitledSession}`}
                        title={t.hub.deleteWarning}
                        className="history-card-confirm-yes"
                        onClick={() => {
                          setConfirmingId(null);
                          onDeleteNotebook(session.notebook_id);
                        }}
                      >
                        <CheckIcon size={12} />
                      </button>
                      <button
                        type="button"
                        aria-label={t.common.cancel}
                        title={t.common.cancel}
                        className="history-card-confirm-no"
                        onClick={() => setConfirmingId(null)}
                        autoFocus
                      >
                        <CloseIcon size={12} />
                      </button>
                    </div>
                  ) : (
                    (isHovered || isActive) && !isGuest && renamingId !== session.notebook_id && (
                      <>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            cancelled.current = false;
                            setDraft(session.title);
                            setRenamingId(session.notebook_id);
                          }}
                          title={t.hub.rename}
                          aria-label={`${t.hub.rename}: ${session.title || t.sidebar.untitledSession}`}
                          className="history-card-del-btn history-card-rename-btn"
                        >
                          <PencilIcon size={12} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmingId(session.notebook_id);
                          }}
                          title={(session.processing_count ?? 0) > 0 ? t.hub.deleteBlocked : t.sidebar.deleteSession}
                          aria-label={`${t.common.delete}: ${session.title || t.sidebar.untitledSession}`}
                          className="history-card-del-btn"
                          disabled={(session.processing_count ?? 0) > 0}
                        >
                          <TrashIcon size={12} />
                        </button>
                      </>
                    )
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 4. Secure Workspace Footer */}
      <div className="history-footer">
        <div className="history-footer-status">
          <span className="history-footer-dot" />
          <span>{t.sidebar.workspaceActive}</span>
        </div>
        <span className="history-footer-tag">{t.sidebar.encrypted}</span>
      </div>
    </div>
  );
};
