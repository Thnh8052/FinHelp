import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { ChatSession } from "../../types/chat";
import { MessageSquareIcon, PlusIcon, TrashIcon } from "../common/Icons";
import "./chat.css";

interface ChatHistoryListProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  isGuest?: boolean;
}

/**
 * Analysis sessions history list
 * Provides "New Analysis" button, session cards with metadata, and secure workspace footer.
 */
export const ChatHistoryList: React.FC<ChatHistoryListProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isGuest = false,
}) => {
  const { t, lang } = useLanguage();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSessions = sessions.filter((s) =>
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
        <span className="history-section-count">{sessions.length} {t.sidebar.sessionsCount}</span>
      </div>

      {/* Search Filter */}
      {sessions.length >= 3 && (
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
        {filteredSessions.length === 0 ? (
          <div className="history-empty">
            {searchTerm
              ? t.sidebar.noSessionsMatch
              : t.sidebar.noSessionsYet}
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.session_id === activeSessionId;
            const isHovered = hoveredId === session.session_id;

            return (
              <div
                key={session.session_id}
                onClick={() => onSelectSession(session.session_id)}
                onMouseEnter={() => setHoveredId(session.session_id)}
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
                        onDeleteSession(session.session_id);
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
