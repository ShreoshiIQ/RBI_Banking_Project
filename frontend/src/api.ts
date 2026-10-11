// Thin client for the RegIntel FastAPI backend. The token lives in sessionStorage
// so it disappears when the tab closes.

const TOKEN_KEY = "regintel.token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the session lasts for this page only */
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1${path}`, { ...init, headers });
  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("regintel:signed-out"));
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep status text */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  upload: <T>(path: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<T>(path, { method: "POST", body: form });
  },
  login: async (username: string, password: string) => {
    const form = new URLSearchParams({ username, password });
    const response = await fetch("/api/v1/auth/login", { method: "POST", body: form });
    if (!response.ok) throw new ApiError(response.status, response.status === 401 ? "Wrong username or password." : "Sign-in failed. Try again.");
    const body = (await response.json()) as { access_token: string };
    setToken(body.access_token);
  },
};
