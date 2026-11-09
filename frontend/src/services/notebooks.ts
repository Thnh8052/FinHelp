import { apiRequest } from "./api";
import { Notebook } from "../types/notebook";

export const notebookService = {
  list: () => apiRequest<Notebook[]>("/notebooks"),
  get: (notebookId: string) => apiRequest<Notebook>(`/notebooks/${notebookId}`),
  create: () => apiRequest<Notebook>("/notebooks", { method: "POST", body: JSON.stringify({}) }),
  remove: (notebookId: string) => apiRequest<{ success: boolean }>(`/notebooks/${notebookId}`, { method: "DELETE" }),
  createGuest: () => apiRequest<Notebook>("/notebooks/guest", { method: "POST" }),
};

// Mỗi khách chưa đăng nhập có notebook riêng do backend cấp (nb_guest_ + 32 ký tự ngẫu nhiên): mã đó là chìa khóa của khách,
// lưu trong trình duyệt; khách này không thấy tài liệu và hội thoại của khách khác.
const GUEST_NOTEBOOK_KEY = "finanalyst_guest_notebook";
const ACTIVE_NOTEBOOK_KEY = "finanalyst_active_notebook";

const readKey = (key: string): string | null => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};
const writeKey = (key: string, value: string | null) => {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* trình duyệt chặn lưu trữ: lần tải sau mở notebook đầu tiên */
  }
};

/** Đoạn chat đang mở, để F5 quay lại đúng chỗ. */
export const activeNotebookStore = {
  get: (): string | null => readKey(ACTIVE_NOTEBOOK_KEY),
  set: (notebookId: string) => writeKey(ACTIVE_NOTEBOOK_KEY, notebookId),
};

/** Notebook của khách này: dùng lại mã đã lưu nếu backend còn nhận, nếu không xin notebook mới. null khi không lấy được. */
export async function guestNotebook(): Promise<Notebook | null> {
  const saved = readKey(GUEST_NOTEBOOK_KEY);
  if (saved) {
    try {
      return await notebookService.get(saved);
    } catch {
      /* mã cũ không còn dùng được (ví dụ đã hết hạn 24 giờ): xin notebook mới */
    }
  }
  try {
    const notebook = await notebookService.createGuest();
    writeKey(GUEST_NOTEBOOK_KEY, notebook.notebook_id);
    return notebook;
  } catch {
    return null;
  }
}
