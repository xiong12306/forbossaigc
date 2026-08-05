const TOKEN_KEY = "bossaigc_token";
const USER_KEY = "bossaigc_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getUser(): string | null {
  return localStorage.getItem(USER_KEY);
}

export function setUser(username: string) {
  localStorage.setItem(USER_KEY, username);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

export async function login(username: string, password: string): Promise<{ access_token: string; username: string }> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "登录失败" }));
    throw new Error(err.detail || `登录失败 (${res.status})`);
  }
  const data = await res.json();
  setToken(data.access_token);
  setUser(data.username);
  return data;
}

export function logout() {
  clearToken();
  window.location.href = "/login";
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
