import React from "react";
import { useLanguage } from "../../context/LanguageContext";
import { CitationItem } from "../../types/chat";
import "./chat.css";

interface CitationBadgeProps {
  citation: CitationItem;
  onClick: () => void;
  index?: number;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({ citation, onClick, index }) => {
  const { t } = useLanguage();
  return (
    <button
      type="button"
      onClick={onClick}
      title={t.workspace.citationTitle.replace("{n}", String(index ?? "")).replace("{page}", String(citation.page))}
      className="citation-badge"
    >
      {index && <span className="citation-badge-index">[{index}]</span>}
      <span className="citation-badge-page">{t.workspace.pageLabel} {citation.page}</span>
    </button>
  );
};
