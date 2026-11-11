import type { TranslationSchema } from "../locales/types";

const API_BASE = "/api/v1";

/** The blanks of a sentence: `{name}` in the sentence is filled from `params.name`. */
export type ErrorParams = Record<string, string | number>;

/** One refused field of a form (422): its code names the sentence, as for any error. */
export interface FieldError {
  field: string;
  code: string;
  params: ErrorParams;
}

/**
 * A non-2xx answer. `status` is the HTTP code; `code` names what went wrong (backend/app/core/error_codes.py) and `params` fill its
 * sentence. The server's own text never reaches the screen: `errorText` turns the code into the interface's language.
 * `fields`: the refused fields of a form, each with its own code.
 */
export class ApiError extends Error {
  status: number;
  code?: string;
  params: ErrorParams;
  fields: FieldError[];

  constructor(status: number, code?: string, params: ErrorParams = {}, fields: FieldError[] = []) {
    super(code || `Request failed with status ${status}`);
    this.status = status;
    this.code = code;
    this.params = params;
    this.fields = fields;
  }
}

/** Refusals where signing in can help: a session that ended, a sign-in-only feature, a guest's limit. */
const SIGN_IN_CODES = new Set(["login_required", "session_expired", "guest_allowance_used", "guest_document_limit"]);
export const signInHelps = (err: ApiError): boolean => err.status === 401 || SIGN_IN_CODES.has(err.code ?? "");

/** The sentence for `code` with its blanks filled; undefined when the code has no sentence. */
function sentence(t: TranslationSchema, code: string, params: ErrorParams): string | undefined {
  const table = t.errors as Record<string, string>;
  if (!Object.prototype.hasOwnProperty.call(table, code)) return undefined;
  return table[code].replace(/\{(\w+)\}/g, (_, key: string) => String(params[key] ?? ""));
}

/** What to show for an error: the sentence for its code, else `fallback`. Never the code or the server's own text. */
export function errorText(err: unknown, t: TranslationSchema, fallback: string): string {
  if (!(err instanceof ApiError) || !err.code) return fallback;
  return sentence(t, err.code, err.params) ?? fallback;
}

/** One refused form field in words; a code without a sentence reads as "not valid". */
export function fieldErrorText(field: FieldError, t: TranslationSchema): string {
  return sentence(t, field.code, field.params) ?? sentence(t, "invalid_field", {}) ?? "";
}

/** A document's stored failure (its error_message is a code). Text stored before codes existed gets the generic sentence. */
export function processingErrorText(code: string, t: TranslationSchema): string {
  return sentence(t, code, {}) ?? sentence(t, "ingestion_unexpected", {}) ?? "";
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
    // The backend names the error by code (and each refused field by its own code); the sentences come from the locales
    const body = errorData.detail && typeof errorData.detail === "object" ? errorData.detail : {};
    throw new ApiError(response.status, typeof body.code === "string" ? body.code : undefined, body.params ?? {}, body.fields ?? []);
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
