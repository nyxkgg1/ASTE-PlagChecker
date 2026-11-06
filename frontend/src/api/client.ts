// All backend calls go through this file.
// In development Vite proxies /auth, /admin, /reference and /scans to
// FastAPI. For production set VITE_API_BASE_URL (and enable CORS in main.py
// if the frontend is served from a different origin).

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "aste_plag_token";

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Called when the backend answers 401 so the app can return to login.
let unauthorizedHandler: (() => void) | null = null;
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc, msg, type}]
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return fallback;
}

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = detailToMessage(body?.detail, message);
    } catch {
      /* non-JSON error body */
    }
    if (response.status === 401 && token && unauthorizedHandler) {
      unauthorizedHandler();
    }
    throw new ApiError(response.status, message);
  }
  return response;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await raw(path);
  return (await response.json()) as T;
}


export async function apiGetBlob(path: string): Promise<Blob> {
  const response = await raw(path);
  return response.blob();
}



export async function apiSend<T>(
  method: "POST" | "PATCH" | "DELETE" | "PUT",
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await raw(path, {
    method,
    headers:
      body === undefined
        ? undefined
        : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await response.text();

  let result: unknown;

  if (text) {
    try {
      result = JSON.parse(text);
    } catch {
      result = text;
    }
  }

  if (!response.ok) {
    const payload = result as
      | { detail?: unknown; message?: unknown }
      | string
      | undefined;

    const message =
      typeof payload === "string"
        ? payload
        : typeof payload?.detail === "string"
          ? payload.detail
          : typeof payload?.message === "string"
            ? payload.message
            : `Request failed with HTTP ${response.status}`;

    throw new Error(message);
  }

  return result as T;
}


export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const response = await raw(path, { method: "POST", body: form });
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// Authenticated file download (the browser cannot add the Bearer header to
// a plain <a href>, so fetch the blob and save it).
export async function apiDownload(path: string, fallbackName: string): Promise<void> {
  const response = await raw(path);
  const blob = await response.blob();

  let filename = fallbackName;
  const disposition = response.headers.get("Content-Disposition");
  const match = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  if (match) filename = decodeURIComponent(match[1]);

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}
