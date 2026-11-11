const API_BASE = "/api/v1";

/** A non-2xx answer: `status` is the HTTP code, `detail` the message the backend sent (undefined when it sent none). */
export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, detail?: string) {
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
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
    // A refused form field answers with a list of technical errors, not a sentence for the user
    throw new ApiError(response.status, typeof errorData.detail === "string" ? errorData.detail : undefined);
  }

  return response;
}

export async function apiRequest<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  return (await send(endpoint, options)).json();
}

/** A file behind sign-in: the token travels in a header, never in an address. */
export async function apiBlob(endpoint: string): Promise<Blob> {
  return (await send(endpoint)).blob();
}
