import { useCallback, useState } from "react";
import { ToastData } from "../components/common/Toast";

export type ShowToast = (message: string, type?: ToastData["type"], actionLabel?: string, onAction?: () => void) => void;

/** Thông báo dạng thanh nhỏ ở giữa phía trên (thay hoàn toàn pop-up của trình duyệt). */
export function useToast() {
  const [toast, setToast] = useState<ToastData | null>(null);

  const showToast: ShowToast = useCallback((message, type = "info", actionLabel, onAction) => {
    setToast({ id: `toast_${Date.now()}`, message, type, actionLabel, onAction });
  }, []);

  // One function for the life of the hook: Toast restarts its 5 s timer whenever `onClose` changes, so a new one on every render (each poll of the
  // workspace) kept the toast on screen for ever
  const closeToast = useCallback(() => setToast(null), []);

  return { toast, showToast, closeToast };
}
