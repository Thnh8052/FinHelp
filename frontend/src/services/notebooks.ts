import { apiRequest } from "./api";
import { Notebook } from "../types/notebook";

export const notebookService = {
  list: () => apiRequest<Notebook[]>("/notebooks"),
  get: (notebookId: string) => apiRequest<Notebook>(`/notebooks/${notebookId}`),
  createGuest: () => apiRequest<Notebook>("/notebooks/guest", { method: "POST" }),
};

// Mỗi khách chưa đăng nhập có notebook riêng do backend cấp (nb_guest_ + 32 ký tự ngẫu nhiên): mã đó là chìa khóa của khách,
// lưu trong trình duyệt; khách này không thấy tài liệu và hội thoại của khách khác.
const GUEST_NOTEBOOK_KEY = "finanalyst_guest_notebook";
const GUEST_SESSION_KEY = "finanalyst_guest_session";

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
    /* trình duyệt chặn lưu trữ: khách nhận notebook mới ở lần tải sau */
  }
};

export const guestStore = {
  session: (): string | null => readKey(GUEST_SESSION_KEY),
  setSession: (sessionId: string | null) => writeKey(GUEST_SESSION_KEY, sessionId),
};

/** Notebook của khách này: dùng lại mã đã lưu nếu backend còn nhận, nếu không xin notebook mới. null khi không lấy được. */
export async function guestNotebookId(): Promise<string | null> {
  const saved = readKey(GUEST_NOTEBOOK_KEY);
  if (saved) {
    try {
      await notebookService.get(saved);
      return saved;
    } catch {
      /* mã cũ không còn dùng được: xin notebook mới */
    }
  }
  try {
    const nb = await notebookService.createGuest();
    writeKey(GUEST_NOTEBOOK_KEY, nb.notebook_id);
    writeKey(GUEST_SESSION_KEY, null);
    return nb.notebook_id;
  } catch {
    return null;
  }
}
