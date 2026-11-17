import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { AnswerActions as Actions } from "../../types/chat";

interface AnswerActionsProps {
  actions: Actions;
  disabled: boolean;
  /** Ask the same question again over the ticked sources (they become @ tags), or search deeper over the same sources. */
  onAsk: (sources: string[], deeper: boolean) => void;
  /** Put the question back in the input box. */
  onEdit: () => void;
}

/** The buttons under an answer (docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md 4.2): a source chooser where several sources can be ticked
 * (a question about two companies needs two), "search deeper", and "edit the question". One click per answer: the server refuses a second one. */
export const AnswerActions: React.FC<AnswerActionsProps> = ({ actions, disabled, onAsk, onEdit }) => {
  const { t } = useLanguage();
  const chooser = actions.chooser || [];
  const [ticked, setTicked] = useState<string[]>(() => chooser.filter((c) => c.checked).map((c) => c.document_id));
  const prominent = !!actions.search_more?.prominent;
  if (!chooser.length && !actions.search_more && !actions.edit_question) return null;
  const toggle = (id: string) => setTicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  return (
    <div className="chat-answer-actions">
      {actions.search_more && (
        <button
          type="button"
          className={prominent ? "chat-sample-btn chat-action-prominent" : "chat-action-subtle"}
          disabled={disabled}
          onClick={() => onAsk([], true)}
        >
          {t.workspace.searchDeeper}
        </button>
      )}
      {actions.edit_question && (
        <button type="button" className="chat-action-subtle" disabled={disabled} onClick={onEdit}>
          {t.workspace.editQuestion}
        </button>
      )}
      {chooser.length > 0 && (
        <details className="chat-chooser" open={prominent}>
          <summary>{t.workspace.changeSources}</summary>
          <fieldset>
            <legend className="sr-only">{t.workspace.chooseSourcesLegend}</legend>
            {chooser.map((c) => (
              <label key={c.document_id} className="chat-chooser-row">
                <input type="checkbox" checked={ticked.includes(c.document_id)} onChange={() => toggle(c.document_id)} disabled={disabled} />
                <span>{c.label}</span>
              </label>
            ))}
          </fieldset>
          <button type="button" className="chat-sample-btn" disabled={disabled || ticked.length === 0} onClick={() => onAsk(ticked, false)}>
            {t.workspace.askAgainWith.replace("{n}", String(ticked.length))}
          </button>
        </details>
      )}
    </div>
  );
};
