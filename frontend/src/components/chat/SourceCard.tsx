import React from "react";
import { ArrowRight } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { CitationItem } from "../../types/chat";
import "./chat.css";

interface SourceCardProps {
  citation: CitationItem;
  /** The [n] the answer's text uses for this excerpt. */
  index: number;
  /** File name of the cited report (unknown once the report is removed from the chat). */
  fileName?: string;
  onClick: () => void;
}

/** One cited excerpt under an answer: its number, the report it is from, the page. Opens that page in the source preview. */
export const SourceCard: React.FC<SourceCardProps> = ({ citation, index, fileName, onClick }) => {
  const { t } = useLanguage();
  return (
    <button
      type="button"
      onClick={onClick}
      title={t.workspace.citationTitle.replace("{n}", String(index)).replace("{page}", String(citation.page))}
      className="source-card"
    >
      <span className="source-card-index">{index}</span>
      <span className="source-card-text">
        {fileName && <b className="source-card-file">{fileName}</b>}
        <small>{t.workspace.pageLabel} {citation.page}</small>
      </span>
      <ArrowRight size={16} className="source-card-arrow" aria-hidden />
    </button>
  );
};
