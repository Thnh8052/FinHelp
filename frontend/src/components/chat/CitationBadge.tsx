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
      title={`View source citation [${index || ""}] at Page ${citation.page}`}
      className="citation-badge"
    >
      {index && <span className="citation-badge-index">[{index}]</span>}
      <span className="citation-badge-page">Page {citation.page}</span>
    </button>
  );
};
