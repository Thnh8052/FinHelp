import { apiRequest } from "./api";
import { Notebook } from "../types/notebook";

export const notebookService = {
  list: () => apiRequest<Notebook[]>("/notebooks"),
  get: (notebookId: string) => apiRequest<Notebook>(`/notebooks/${notebookId}`),
  create: () => apiRequest<Notebook>("/notebooks", { method: "POST", body: JSON.stringify({}) }),
  rename: (notebookId: string, title: string) =>
    apiRequest<{ success: boolean }>(`/notebooks/${notebookId}`, { method: "PUT", body: JSON.stringify({ title }) }),
  remove: (notebookId: string) => apiRequest<{ success: boolean }>(`/notebooks/${notebookId}`, { method: "DELETE" }),
  createGuest: () => apiRequest<Notebook>("/notebooks/guest", { method: "POST" }),
};

// Mỗi khách chưa đăng nhập có notebook riêng do backend cấp (nb_guest_ + 32 ký tự ngẫu nhiên): mã đó là chìa khóa của khách,
// lưu trong trình duyệt; khách này không thấy tài liệu và hội thoại của khách khác.
const GUEST_NOTEBOOK_KEY = "finanalyst_guest_notebook";

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

/** Một sổ tay còn trống nếu đã có, nếu không thì tạo mới: bấm "Mới" nhiều lần không sinh hàng loạt đoạn chat rỗng. */
export async function emptyOrNewNotebook(): Promise<Notebook> {
  const empty = (await notebookService.list()).find((n) => !n.message_count && !n.document_count);
  return empty ?? notebookService.create();
}

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
