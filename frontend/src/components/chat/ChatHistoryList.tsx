import React, { useState } from "react";
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
 * Danh sách đoạn chat (ChatGPT / Claude Style)
 * Cung cấp nút "+ Thêm đoạn chat mới" nổi bật ở đầu danh sách,
 * hiển thị các phiên chat với tiêu đề, biểu tượng và nút xóa khi di chuột.
 */
export const ChatHistoryList: React.FC<ChatHistoryListProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  isGuest = false,
}) => {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const filteredSessions = sessions.filter((s) =>
    (s.title || "").toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="history-container">
      {/* Top: Nút 'Thêm đoạn chat mới' chuẩn phong cách ChatGPT / Claude */}
      <button onClick={onNewChat} className="history-new-btn">
        <div className="history-new-btn-left">
          <PlusIcon size={14} color="var(--accent-primary)" />
          <span>Thêm đoạn chat mới</span>
        </div>
        <span className="history-new-tag">
          {isGuest ? "Cần login" : "New"}
        </span>
      </button>

      {/* Tìm kiếm đoạn chat (nếu có từ 3 đoạn chat trở lên) */}
      {sessions.length >= 3 && (
        <div className="history-search-box">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Tìm kiếm đoạn chat..."
            className="history-search-input"
          />
        </div>
      )}

      {/* Header đề mục */}
      <div className="history-header">
        <span className="history-header-title">
          {searchTerm ? `Kết quả (${filteredSessions.length})` : `Gần đây (${sessions.length})`}
        </span>
      </div>

      {/* Guest Mode Banner nếu chưa đăng nhập */}
      {isGuest && (
        <div className="history-guest-banner">
          <div className="history-guest-badge">
            Chế độ dùng thử
          </div>
          <div>Giới hạn 1 đoạn chat & 1 tài liệu. Đăng nhập để tạo nhiều đoạn chat và lưu lịch sử vĩnh viễn.</div>
        </div>
      )}

      {/* Danh sách các phiên hội thoại (ChatGPT / Claude Style) */}
      <div className="history-list">
        {filteredSessions.length === 0 ? (
          <div className="history-empty">
            {searchTerm
              ? "Không tìm thấy đoạn chat phù hợp."
              : 'Chưa có đoạn chat nào trong sổ tay này. Bấm "Thêm đoạn chat mới" để bắt đầu.'}
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
                className={`history-item ${isActive ? "active" : ""}`}
              >
                {/* Session Icon & Title */}
                <div className="history-item-content">
                  <MessageSquareIcon
                    size={14}
                    color={isActive ? "var(--accent-primary)" : "var(--text-dim)"}
                  />
                  <span
                    className="history-item-title"
                    title={session.title || "Đoạn chat tài chính"}
                  >
                    {session.title || "Đoạn chat tài chính"}
                  </span>
                </div>

                {/* Nút Xóa (xuất hiện khi di chuột hoặc active) */}
                {(isHovered || isActive) && !isGuest && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteSession(session.session_id);
                    }}
                    title="Xóa đoạn chat này"
                    className="history-delete-btn"
                  >
                    <TrashIcon size={12} />
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
