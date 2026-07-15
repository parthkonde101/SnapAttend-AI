import { getToken } from "@/lib/auth";
import { API_BASE_URL } from "@/lib/config";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Attach the stored bearer token, if present. Defaults to true. */
  authenticated?: boolean;
}

/** Parse a fetch Response into typed JSON, or throw a normalized ApiError. */
async function parseResponse<T>(response: Response): Promise<T> {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && "detail" in payload && String(payload.detail)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status);
  }

  return payload as T;
}

/**
 * Thin fetch wrapper around the FastAPI backend. Centralizes base URL
 * resolution, JSON encoding/decoding, auth header injection, and error
 * normalization so callers just deal with typed data or an ApiError.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, authenticated = true, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  finalHeaders.set("Content-Type", "application/json");

  if (authenticated) {
    const token = getToken();
    if (token) {
      finalHeaders.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return parseResponse<T>(response);
}

/**
 * Fetches a binary resource (e.g. an attendance photo) with the same auth
 * header `apiRequest` attaches, returning an object URL the caller can hand
 * straight to an <img src>. Separate from `apiRequest` because the response
 * here is never JSON — an <img> tag can't attach an Authorization header
 * itself, so this is the one place a protected image has to be fetched as a
 * blob first. Caller is responsible for revoking the returned URL
 * (`URL.revokeObjectURL`) once it's no longer displayed, to avoid leaking
 * memory across repeated opens.
 */
export async function fetchAuthenticatedImageUrl(path: string): Promise<string> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

/** Pulls the `filename="..."` part out of a Content-Disposition header, if present. */
function extractFilename(contentDisposition: string | null, fallback: string): string {
  if (!contentDisposition) return fallback;
  const match = contentDisposition.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : fallback;
}

/**
 * Fetches a protected file (e.g. the attendance Excel export) with the same
 * auth header `apiRequest` attaches, then immediately triggers a browser
 * download — a plain `<a href>` can't attach an Authorization header
 * itself, so, like `fetchAuthenticatedImageUrl`, this has to fetch as a
 * blob first. The filename is read off the server's Content-Disposition
 * header (the backend is the source of truth for the exact
 * `Attendance_<SessionName>_<Date>.xlsx` naming) with `fallbackFilename`
 * used only if that header is somehow missing.
 */
export async function downloadAuthenticatedFile(path: string, fallbackFilename: string): Promise<void> {
  const token = getToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    const isJson = response.headers.get("content-type")?.includes("application/json");
    const payload = isJson ? await response.json().catch(() => null) : null;
    const message =
      (payload && typeof payload === "object" && "detail" in payload && String(payload.detail)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status);
  }

  const filename = extractFilename(response.headers.get("content-disposition"), fallbackFilename);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}

/**
 * Uploads a single file as multipart/form-data (e.g. an attendance photo).
 * Kept separate from `apiRequest` because the browser must set its own
 * `Content-Type` (with boundary) for FormData — sharing `parseResponse`
 * keeps error handling identical between both.
 */
export async function uploadFile<T>(path: string, file: Blob, filename: string): Promise<T> {
  const formData = new FormData();
  formData.append("file", file, filename);

  const headers = new Headers();
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  return parseResponse<T>(response);
}

/**
 * Same as `uploadFile`, plus extra plain-text form fields alongside the
 * file in the same multipart body — e.g. the PRN the student typed,
 * submitted together with their ID photo to
 * POST /auth/student/forgot-password/verify. `authenticated` defaults to
 * false since this specific call happens before the student has any
 * session token at all (that's the whole point of the forgot-password
 * flow); pass `true` for an authenticated variant if a future caller needs it.
 */
export async function uploadFileWithFields<T>(
  path: string,
  file: Blob,
  filename: string,
  fields: Record<string, string>,
  options: { authenticated?: boolean } = {}
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file, filename);
  for (const [key, value] of Object.entries(fields)) {
    formData.append(key, value);
  }

  const headers = new Headers();
  if (options.authenticated) {
    const token = getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: formData,
  });

  return parseResponse<T>(response);
}
