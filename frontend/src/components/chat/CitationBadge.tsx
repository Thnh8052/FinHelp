import React from "react";
import { CitationItem } from "../../types/chat";
import "./chat.css";

interface CitationBadgeProps {
  citation: CitationItem;
  onClick: () => void;
  index?: number;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({ citation, onClick, index }) => {
  return (
    <button
      onClick={onClick}
      title={`Xem nguồn tại Trang ${citation.page}`}
      className="citation-badge"
    >
      <span>{index ? `[${index}]` : `[Trang ${citation.page}]`}</span>
    </button>
  );
};
