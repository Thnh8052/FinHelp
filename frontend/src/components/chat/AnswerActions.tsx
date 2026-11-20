import React, { useState } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { AnswerActions as Actions, AskMode } from "../../types/chat";

interface AnswerActionsProps {
  actions: Actions;
  disabled: boolean;
  /** Ask the same question again: over the ticked sources (no mode: they become @ tags), deeper over the same sources ("deeper"),
   * unchanged after the system could not write an answer ("again"), or over every source of the answer after "the selected sources do not seem
   * to contain this" ("everywhere"). */
  onAsk: (sources: string[], mode?: AskMode) => void;
  /** Put the question back in the input box. */
  onEdit: () => void;
}

/** The buttons under an answer (docs/VERSION_4/CODE_MODEL_DECISIONS_2026-11-17.md 4.2): a source chooser where several sources can be ticked
 * (a question about two companies needs two), "search deeper", and "edit the question". One click per answer: the server refuses a second one.
 * Its children sit in the answer's toolbar (the wrapper is `display: contents`); the chooser takes the last line of it. */
export const AnswerActions: React.FC<AnswerActionsProps> = ({ actions, disabled, onAsk, onEdit }) => {
  const { t } = useLanguage();
  const chooser = actions.chooser || [];
  const prominent = !!actions.search_more?.prominent;
  const [ticked, setTicked] = useState<string[]>(() => chooser.filter((c) => c.checked).map((c) => c.document_id));
  const [open, setOpen] = useState(prominent);
  if (!chooser.length && !actions.search_more && !actions.edit_question && !actions.try_again && !actions.search_all) return null;
  const toggle = (id: string) => setTicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  return (
    <div className="chat-answer-actions">
      {actions.try_again && (
        <button type="button" className="chat-answer-btn is-prominent" disabled={disabled} onClick={() => onAsk([], "again")}>
          {t.workspace.tryAgain}
        </button>
      )}
      {actions.search_all && (
        <button type="button" className="chat-answer-btn is-prominent" disabled={disabled} onClick={() => onAsk([], "everywhere")}>
          {t.workspace.searchAll}
        </button>
      )}
      {actions.search_more && (
        <button
          type="button"
          className={`chat-answer-btn ${prominent ? "is-prominent" : ""}`}
          disabled={disabled}
          onClick={() => onAsk([], "deeper")}
        >
          {t.workspace.searchDeeper}
          <span className="chat-answer-cost">{t.workspace.searchDeeperCost}</span>
        </button>
      )}
      {actions.edit_question && (
        <button type="button" className="chat-answer-btn" disabled={disabled} onClick={onEdit}>
          {t.workspace.editQuestion}
        </button>
      )}
      {chooser.length > 0 && (
        <details className="chat-chooser" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
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
          <button type="button" className="chat-answer-btn is-prominent" disabled={disabled || ticked.length === 0} onClick={() => onAsk(ticked)}>
            {t.workspace.askAgainWith.replace("{n}", String(ticked.length))}
          </button>
        </details>
      )}
    </div>
  );
};
