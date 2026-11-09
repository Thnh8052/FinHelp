import React, { useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Pencil } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { CheckIcon, CloseIcon, FileTextIcon, TrashIcon } from "../../components/common/Icons";
import { Notebook } from "../../types/notebook";

const TITLE_MAX = 120;
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60],
];

/** MongoDB trả thời gian UTC không kèm múi giờ. */
const toDate = (value: string) => new Date(/([zZ]|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);

function timeAgo(value: string, lang: string): string {
  const seconds = (Date.now() - toDate(value).getTime()) / 1000;
  const format = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const unit = UNITS.find(([, size]) => seconds >= size);
  return unit ? format.format(-Math.floor(seconds / unit[1]), unit[0]) : format.format(0, "minute");
}

interface NotebookCardProps {
  notebook: Notebook;
  onRename: (notebookId: string, title: string) => Promise<boolean>;
  onDelete: (notebookId: string) => Promise<void>;
}

/** Một sổ tay trên trang Hub: mở, đổi tên tại chỗ, xóa có bước xác nhận. */
export const NotebookCard: React.FC<NotebookCardProps> = ({ notebook, onRename, onDelete }) => {
  const { t, lang } = useLanguage();
  const [isEditing, setIsEditing] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [draft, setDraft] = useState(notebook.title);
  const [titleError, setTitleError] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const editButton = useRef<HTMLButtonElement>(null);
  const errorId = useId();

  const files = notebook.document_count ?? 0;
  const isProcessing = (notebook.processing_count ?? 0) > 0;

  const startEditing = () => {
    setDraft(notebook.title);
    setTitleError("");
    setIsEditing(true);
  };

  const stopEditing = () => {
    setIsEditing(false);
    requestAnimationFrame(() => editButton.current?.focus());
  };

  const save = async () => {
    const title = draft.trim();
    if (!title) {
      setTitleError(t.hub.titleRequired);
      return;
    }
    if (title === notebook.title) {
      stopEditing();
      return;
    }
    setIsBusy(true);
    const saved = await onRename(notebook.notebook_id, title);
    setIsBusy(false);
    if (saved) stopEditing();
  };

  const confirmDelete = async () => {
    setIsBusy(true);
    await onDelete(notebook.notebook_id);
    setIsBusy(false);
    setIsConfirming(false);
  };

  if (isConfirming) {
    return (
      <li className="hub-card hub-card-confirm">
        <p className="hub-confirm-title">{t.hub.deleteQuestion.replace("{title}", notebook.title)}</p>
        <p className="hub-confirm-note">{t.hub.deleteWarning}</p>
        <div className="hub-confirm-actions">
          <button type="button" className="hub-text-btn" onClick={() => setIsConfirming(false)} disabled={isBusy} autoFocus>
            {t.common.cancel}
          </button>
          <button type="button" className="hub-text-btn hub-text-btn-danger" onClick={confirmDelete} disabled={isBusy}>
            {t.common.delete}
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="hub-card">
      <div className="hub-card-head">
        <span className="hub-card-icon" aria-hidden="true">
          <FileTextIcon size={15} />
        </span>
        {isEditing ? (
          <div className="hub-rename">
            <input
              className="hub-input"
              value={draft}
              maxLength={TITLE_MAX}
              autoFocus
              aria-label={t.hub.renameLabel}
              aria-invalid={!!titleError}
              aria-describedby={titleError ? errorId : undefined}
              onFocus={(e) => e.target.select()}
              onChange={(e) => {
                setDraft(e.target.value);
                setTitleError("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") void save();
                if (e.key === "Escape") stopEditing();
              }}
            />
            {titleError && <p id={errorId} className="hub-field-error">{titleError}</p>}
          </div>
        ) : (
          <h2 className="hub-card-title">
            <Link to={`/app/${notebook.notebook_id}`} className="hub-card-link" title={notebook.title}>
              {notebook.title}
            </Link>
          </h2>
        )}
      </div>

      <div className="hub-card-foot">
        <p className="hub-card-meta">
          <span>{(files === 1 ? t.hub.fileOne : t.hub.fileMany).replace("{n}", String(files))}</span>
          <span aria-hidden="true">·</span>
          <time dateTime={toDate(notebook.updated_at).toISOString()}>{timeAgo(notebook.updated_at, lang)}</time>
          {isProcessing && (
            <span className="hub-card-processing">
              <span className="chat-processing-spinner" aria-hidden="true" />
              {t.hub.processing}
            </span>
          )}
        </p>

        <div className="hub-card-actions">
          {isEditing ? (
            <>
              <button type="button" className="hub-icon-btn" aria-label={t.common.save} title={t.common.save} onClick={save} disabled={isBusy}>
                <CheckIcon size={14} />
              </button>
              <button type="button" className="hub-icon-btn" aria-label={t.common.cancel} title={t.common.cancel} onClick={stopEditing} disabled={isBusy}>
                <CloseIcon size={14} />
              </button>
            </>
          ) : (
            <>
              <button ref={editButton} type="button" className="hub-icon-btn" aria-label={`${t.hub.rename}: ${notebook.title}`} title={t.hub.rename} onClick={startEditing}>
                <Pencil size={14} aria-hidden="true" />
              </button>
              <button
                type="button"
                className="hub-icon-btn hub-icon-btn-danger"
                aria-label={`${t.common.delete}: ${notebook.title}`}
                title={isProcessing ? t.hub.deleteBlocked : t.common.delete}
                onClick={() => setIsConfirming(true)}
                disabled={isProcessing}
              >
                <TrashIcon size={14} />
              </button>
            </>
          )}
        </div>
      </div>
    </li>
  );
};
