import React from "react";
import { ArrowRight, Banknote, Check, FileText, Lock, Search, TrendingUp, Upload } from "lucide-react";
import { useLanguage } from "../../context/LanguageContext";
import { usePdfDrop } from "../../hooks/usePdfDrop";
import { processingErrorText } from "../../services/api";
import { DocumentRecord, isDocFailed, isDocProcessing } from "../../types/notebook";
import "./chat.css"; // the spinner of a report being processed
import "./start.css";

interface StartScreenProps {
  documents: DocumentRecord[];
  isUploading: boolean;
  isGuest: boolean;
  /** The limits shown come from the account's quota, never from a copy of them here. */
  maxSources: number;
  maxFileSizeMb: number;
  onUploadFiles: (files: File[]) => void;
  /** Opens the Sources drawer (where a report is deleted or chosen). */
  onManage: () => void;
  /** An example question goes into the question box. It is asked only once a report is ready. */
  onPickQuestion: (question: string) => void;
}

const formatFileSize = (bytes?: number) => (bytes ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : "0 MB");

/**
 * What a chat shows before its first question: add a report, then ask. Step 1 is current until a report is ready, then step 2.
 * (Step 3 is the answer itself: this screen is gone by then.)
 */
export const StartScreen: React.FC<StartScreenProps> = ({
  documents,
  isUploading,
  isGuest,
  maxSources,
  maxFileSizeMb,
  onUploadFiles,
  onManage,
  onPickQuestion,
}) => {
  const { t } = useLanguage();
  const isBusy = isUploading || documents.some(isDocProcessing);
  const { isDragging, inputRef, dropHandlers, onInputChange, openPicker } = usePdfDrop(onUploadFiles, isBusy);
  const hasReady = documents.some((d) => d.status === "ready");
  const currentStep = hasReady ? 2 : 1;
  const hasFiles = documents.length > 0;
  const canAddMore = documents.length < maxSources;

  const limitsText = (isGuest
    ? maxSources === 1 ? t.start.limitsGuestOne : t.start.limitsGuestMany
    : maxSources === 1 ? t.start.limitsMemberOne : t.start.limitsMemberMany
  ).replace("{mb}", String(maxFileSizeMb)).replace("{n}", String(maxSources));

  const steps = [t.start.step1, t.start.step2, t.start.step3];
  const questions = [
    { icon: TrendingUp, title: t.start.q1Title, text: t.start.q1Text },
    { icon: Banknote, title: t.start.q2Title, text: t.start.q2Text },
    { icon: Search, title: t.start.q3Title, text: t.start.q3Text },
  ];

  const statusLabel = (d: DocumentRecord) =>
    d.status === "pending" ? (d.queue_ahead ? t.sourcesDrawer.queuedAhead.replace("{n}", String(d.queue_ahead)) : t.sourcesDrawer.queued)
      : isDocProcessing(d) ? t.sourcesDrawer.processingDots
      : isDocFailed(d) ? t.sourcesDrawer.failedBadge
      : t.sourcesDrawer.statusReady;

  return (
    <div className="start-screen">
      <p className="start-eyebrow">{t.start.eyebrow}</p>
      <h2 className="start-title">{t.start.title}</h2>
      <p className="start-lead">{t.start.lead}</p>

      <ol className="start-steps" aria-label={t.start.stepsLabel}>
        {steps.map((label, i) => {
          const n = i + 1;
          const state = n < currentStep ? "done" : n === currentStep ? "current" : "todo";
          return (
            <li key={n} className={`start-step ${state}`} aria-current={state === "current" ? "step" : undefined}>
              <span className="start-step-dot">{state === "done" ? <Check size={14} aria-hidden /> : n}</span>
              <span className="start-step-label">{label}</span>
            </li>
          );
        })}
      </ol>

      <section className="start-upload">
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf"
          disabled={isBusy}
          onChange={onInputChange}
          hidden
        />

        {hasFiles && (
          <ul className="start-files">
            {documents.map((d) => (
              <li key={d.document_id} className="start-file">
                <FileText size={20} className="start-file-icon" aria-hidden />
                <div className="start-file-text">
                  <b className="start-file-name" title={d.file_name}>{d.file_name}</b>
                  <small>
                    {[d.page_count ? t.sourcesDrawer.pagesCount.replace("{n}", String(d.page_count)) : "", formatFileSize(d.file_size_bytes)].filter(Boolean).join(" · ")}
                  </small>
                  {isDocFailed(d) && d.error_message && <small className="start-file-error">{processingErrorText(d.error_message, t)}</small>}
                </div>
                <span className={`start-file-status ${d.status}`} role={isDocProcessing(d) ? "status" : undefined}>
                  {isDocProcessing(d) && <span className="chat-processing-spinner" aria-hidden />}
                  {statusLabel(d)}
                </span>
              </li>
            ))}
          </ul>
        )}

        {!hasFiles ? (
          <div className={`start-drop ${isDragging ? "dragging" : ""}`} {...dropHandlers}>
            <span className="start-drop-tile" aria-hidden><Upload size={24} /></span>
            <h3 className="start-drop-title">{isDragging ? t.start.dropTitleActive : t.start.dropTitle}</h3>
            <p className="start-drop-sub">{t.start.dropSub}</p>
            <button type="button" className="start-btn" onClick={openPicker} disabled={isBusy}>
              <Upload size={16} aria-hidden />
              {t.start.chooseBtn}
            </button>
            <small className="start-drop-limits">{limitsText}</small>
          </div>
        ) : (
          <div className={`start-strip ${isDragging ? "dragging" : ""}`} {...dropHandlers}>
            {canAddMore && (
              <button type="button" className="start-btn outline" onClick={openPicker} disabled={isBusy}>
                <Upload size={16} aria-hidden />
                {t.start.addAnother}
              </button>
            )}
            <small className="start-drop-limits">{limitsText}</small>
            <button type="button" className="start-link" onClick={onManage}>
              {t.nav.manageSources}
            </button>
          </div>
        )}
      </section>

      <p className="start-under">
        <Lock size={15} aria-hidden />
        {t.start.isolated}
      </p>

      <section className="start-questions">
        <h3 className="start-questions-title">{t.start.questionsTitle}</h3>
        <p className="start-questions-sub">{hasReady ? t.start.questionsSubReady : t.start.questionsSubNoReport}</p>
        <div className="start-grid">
          {questions.map(({ icon: Icon, title, text }) => (
            <button key={title} type="button" className="start-q" onClick={() => onPickQuestion(text)} title={t.start.useQuestion}>
              <Icon size={22} className="start-q-icon" aria-hidden />
              <ArrowRight size={16} className="start-q-arrow" aria-hidden />
              <b>{title}</b>
              <span>{text}</span>
            </button>
          ))}
        </div>
      </section>

      <p className="start-fine">{t.start.disclaimer}</p>
    </div>
  );
};
