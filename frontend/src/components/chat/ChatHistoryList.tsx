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
 * Danh sách đoạn chat (Theo chuẩn Layout Mockup V3)
 * Cung cấp nút nổi bật "Tạo đoạn chat mới" ở đầu danh sách (có hiệu ứng hover xoay icon + badge New),
 * danh sách phiên dạng Card với metadata BCTC riêng, và Footer trạng thái hệ thống.
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
      {/* 1. NÚT DUY NHẤT TẠO CHAT MỚI (Mockup V3) */}
      <div className="history-top-section">
        <button
          type="button"
          onClick={onNewChat}
          className="history-new-btn group"
          title="Tạo phiên hội thoại mới"
        >
          <div className="history-new-btn-left">
            <PlusIcon size={16} className="history-plus-icon" />
            <span>Tạo đoạn chat mới</span>
          </div>
          <span className="history-new-tag">
            {isGuest ? "Login" : "New"}
          </span>
        </button>
      </div>

      {/* 2. Tiêu đề danh mục Lịch sử hội thoại */}
      <div className="history-section-header">
        <span className="history-section-title">Lịch sử hội thoại</span>
        <span className="history-section-count">{sessions.length} phiên</span>
      </div>

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

      {/* Guest Mode Banner nếu chưa đăng nhập */}
      {isGuest && (
        <div className="history-guest-banner">
          <div className="history-guest-badge">Chế độ dùng thử</div>
          <div>Giới hạn 1 đoạn chat & 1 tài liệu. Đăng nhập để lưu lịch sử vĩnh viễn.</div>
        </div>
      )}

      {/* 3. Danh sách các phiên hội thoại (Cards chuẩn Mockup V3) */}
      <div className="history-list scrollbar-slim">
        {filteredSessions.length === 0 ? (
          <div className="history-empty">
            {searchTerm
              ? "Không tìm thấy đoạn chat phù hợp."
              : 'Chưa có đoạn chat nào. Bấm "Tạo đoạn chat mới" ở trên để bắt đầu.'}
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
                        title={session.title || "Đoạn chat tài chính"}
                      >
                        {session.title || "Đoạn chat tài chính"}
                      </p>
                      <p className="history-card-sub">
                        <span>📂 BCTC riêng</span>
                        <span>•</span>
                        <span className={isActive ? "status-active" : "status-saved"}>
                          {isActive ? "Đang mở" : "Đã lưu"}
                        </span>
                      </p>
                    </div>
                  </div>

                  {/* Nút Xóa (xuất hiện khi di chuột hoặc active) */}
                  {(isHovered || isActive) && !isGuest && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSession(session.session_id);
                      }}
                      title="Xóa đoạn chat này"
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

      {/* 4. FOOTER SIDEBAR: TRẠNG THÁI HỆ THỐNG AN TOÀN (Mockup V3) */}
      <div className="history-footer">
        <div className="history-footer-status">
          <span className="history-footer-dot" />
          <span>GPU/VRAM: Ổn định</span>
        </div>
        <span className="history-footer-tag">Docling CPU</span>
      </div>
    </div>
  );
};
