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
