import { apiRequest } from "./api";
import { DocumentRecord } from "../types/notebook";

export const documentService = {
  list: (notebookId: string) => apiRequest<DocumentRecord[]>(`/documents/notebook/${notebookId}`),

  remove: (documentId: string) => apiRequest<{ document_id: string; message: string }>(`/documents/${documentId}`, {
    method: "DELETE",
  }),

  upload: (notebookId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiRequest<{ document_id: string; job_id: string; message: string }>(`/documents/upload/${notebookId}`, {
      method: "POST",
      body: formData,
    });
  },

  getFileUrl: (documentId: string) => `/api/v1/documents/${documentId}/file`,
};
