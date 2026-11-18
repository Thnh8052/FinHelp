import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

/** Drag-and-drop and file-picker handling for PDF uploads: shared by the Sources drawer and the start screen. */
export function usePdfDrop(onUploadFiles: (files: File[]) => void, isBusy: boolean) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const drag = (dragging: boolean) => (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(dragging);
  };

  const dropHandlers = {
    onDragOver: drag(true),
    onDragLeave: drag(false),
    onDrop: (e: DragEvent) => {
      drag(false)(e);
      if (isBusy) return;
      const pdfs = Array.from(e.dataTransfer.files ?? []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      if (pdfs.length > 0) onUploadFiles(pdfs);
    },
  };

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (isBusy || !e.target.files?.length) return;
    const files = Array.from(e.target.files);
    e.target.value = ""; // the same file can be chosen again
    onUploadFiles(files);
  };

  const openPicker = () => {
    if (!isBusy) inputRef.current?.click();
  };

  return { isDragging, inputRef, dropHandlers, onInputChange, openPicker };
}
