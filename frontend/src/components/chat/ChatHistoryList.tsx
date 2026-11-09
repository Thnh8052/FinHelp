import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { Notebook } from "../../types/notebook";
import { MessageSquareIcon, PlusIcon, TrashIcon } from "../common/Icons";
import "./chat.css";

interface ChatHistoryListProps {
  notebooks: Notebook[];
  activeNotebookId: string | null;
  onSelectNotebook: (notebookId: string) => void;
  onNewChat: () => void;
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
  onDeleteNotebook,
  isGuest = false,
}) => {
  const { t, lang } = useLanguage();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

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
          title="Create new analysis session"
        >
          <div className="history-new-btn-left">
            <PlusIcon size={16} className="history-plus-icon" />
            <span>{t.sidebar.newAnalysis}</span>
          </div>
          <span className="history-new-tag">
            {isGuest ? "Login" : "New"}
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
                      <p
                        className="history-card-title"
                        title={session.title || "Financial Session"}
                      >
                        {session.title || "Financial Session"}
                      </p>
                      <p className="history-card-sub">
                        <span>{t.sidebar.isolatedFiling}</span>
                        <span>•</span>
                        <span className={isActive ? "status-active" : "status-saved"}>
                          {isActive ? (lang === "vi" ? "Đang mở" : "Active") : (lang === "vi" ? "Đã lưu" : "Saved")}
                        </span>
                      </p>
                    </div>
                  </div>

                  {/* Delete Button */}
                  {(isHovered || isActive) && !isGuest && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteNotebook(session.notebook_id);
                      }}
                      title="Delete this session"
                      className="history-card-del-btn"
                    >
                      <TrashIcon size={12} />
                    </button>
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
