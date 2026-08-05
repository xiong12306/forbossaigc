/**
 * 平台业务 API 封装
 * 所有接口通过相对路径访问，由 Nginx/Vite proxy 反代到后端
 */

import { getToken, isLoggedIn } from "@/lib/auth";

const API_BASE = "";

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options?.headers as Record<string, string> || {}),
  };
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${url}`, { ...options, headers });
  } catch {
    throw new Error("网络请求失败，请检查网络连接");
  }
  if (res.status === 401) {
    if (isLoggedIn()) {
      localStorage.removeItem("bossaigc_token");
      localStorage.removeItem("bossaigc_user");
    }
    window.location.href = "/login";
    throw new Error("登录已过期，请重新登录");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `请求失败 (${res.status})`);
  }
  return res.json() as Promise<T>;
}

// ---------- Dashboard ----------
export const dashboardApi = {
  overview: (range = "7d") => fetchJSON<any>(`/api/dashboard/overview?range=${range}`),
  salesTrend: (range = "7d") => fetchJSON<any[]>(`/api/dashboard/sales-trend?range=${range}`),
  topProducts: () => fetchJSON<any[]>("/api/dashboard/top-products"),
  recentTasks: () => fetchJSON<any[]>("/api/dashboard/recent-tasks"),
};

// ---------- Products ----------
export const productsApi = {
  list: (search?: string) =>
    fetchJSON<any[]>(`/api/products${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  create: (data: any) =>
    fetchJSON<any>("/api/products", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: any) =>
    fetchJSON<any>(`/api/products/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: number) =>
    fetchJSON<void>(`/api/products/${id}`, { method: "DELETE" }),
  updateStatus: (id: number, status: string) =>
    fetchJSON<any>(`/api/products/${id}/status`, { method: "PUT", body: JSON.stringify({ status }) }),
};

// ---------- Assets ----------
export const assetsApi = {
  list: (type?: string) =>
    fetchJSON<any[]>(`/api/assets${type ? `?asset_type=${type}` : ""}`),
  delete: (id: number) =>
    fetchJSON<void>(`/api/assets/${id}`, { method: "DELETE" }),
};

// ---------- Marketing ----------
export const marketingApi = {
  campaigns: () => fetchJSON<any[]>("/api/marketing/campaigns"),
  createCampaign: (data: any) =>
    fetchJSON<any>("/api/marketing/campaigns", { method: "POST", body: JSON.stringify(data) }),
  coupons: () => fetchJSON<any[]>("/api/marketing/coupons"),
  createCoupon: (data: any) =>
    fetchJSON<any>("/api/marketing/coupons", { method: "POST", body: JSON.stringify(data) }),
};

// ---------- Service ----------
export const serviceApi = {
  messages: () => fetchJSON<any[]>("/api/service/messages"),
  resolveMessage: (id: number) =>
    fetchJSON<any>(`/api/service/messages/${id}/resolve`, { method: "PUT" }),
  faq: () => fetchJSON<any[]>("/api/service/faq"),
  stats: () => fetchJSON<any>("/api/service/stats"),
};

// ---------- Finance ----------
export const financeApi = {
  summary: () => fetchJSON<any>("/api/finance/summary"),
  records: (type?: string) =>
    fetchJSON<any[]>(`/api/finance/records${type ? `?record_type=${type}` : ""}`),
  monthlyComparison: () => fetchJSON<any[]>("/api/finance/monthly-comparison"),
};
