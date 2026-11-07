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
      type="button"
      onClick={onClick}
      title={`Xem nguồn trích dẫn [${index || ""}] tại Trang ${citation.page}`}
      className="citation-badge"
    >
      {index && <span className="citation-badge-index">[{index}]</span>}
      <span className="citation-badge-page">Trang {citation.page}</span>
    </button>
  );
};
