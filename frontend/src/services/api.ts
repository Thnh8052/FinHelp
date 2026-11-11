const API_BASE = "/api/v1";

/**
 * A non-2xx answer: `status` is the HTTP code, `detail` the message the backend sent (undefined when it sent none).
 * `fields`: the messages of a refused form (422 list), for the forms whose backend validators write them for the user.
 */
export class ApiError extends Error {
  status: number;
  detail?: string;
  fields: string[];

  constructor(status: number, detail?: string, fields: string[] = []) {
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
    this.fields = fields;
  }
}

async function send(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const headers: HeadersInit = {
    ...options.headers,
  };

  if (!(options.body instanceof FormData)) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    // A refused form field answers with a list of technical errors, not a sentence for the user: never the detail, only `fields`
    const fields = Array.isArray(errorData.detail)
      ? errorData.detail.map((d: { msg?: string }) => (d.msg || "").replace(/^Value error, /, "")).filter(Boolean)
      : [];
    throw new ApiError(response.status, typeof errorData.detail === "string" ? errorData.detail : undefined, fields);
  }

  return response;
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return (await send(endpoint, options)).json();
}

/** A file behind sign-in, fetched with the session cookie (HttpOnly): never a link whose address carries a token. */
export async function apiBlob(endpoint: string): Promise<Blob> {
  return (await send(endpoint)).blob();
}
