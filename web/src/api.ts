import type { ChatRequest, ChatResponse } from "@/types";
import { getToken } from "@/lib/auth";

const API_BASE = "";

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * 上传图片文件到服务器，返回可访问的 URL
 */
export async function uploadImage(file: File): Promise<string> {
  const formData = new FormData();
  formData.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      headers: { ...authHeaders() },
      body: formData,
    });
  } catch {
    throw new Error("上传失败，请确认网络是否正常。");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `上传失败 (${res.status})`);
  }
  const data = await res.json();
  return data.url as string;
}

/**
 * 调用 /api/chat 与助手对话
 * 后端不可用时抛出友好错误
 * 图片生成耗时较长，设置10分钟超时
 */
export async function chat(
  message: string,
  sessionId?: string,
  images?: string[]
): Promise<ChatResponse> {
  const body: ChatRequest = { message, session_id: sessionId, images };
  // 10分钟超时，图片生成需要较长时间
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 600000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("图片生成超时，请稍后重试。");
    }
    throw new Error("无法连接到 BossAIGC 服务，请确认网络是否正常。");
  }
  clearTimeout(timeoutId);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("登录已过期，请重新登录");
  }
  if (!res.ok) {
    throw new Error(`服务异常 (${res.status})，请稍后再试。`);
  }
  return (await res.json()) as ChatResponse;
}

/**
 * 调用 /api/reset 重置会话
 */
export async function reset(sessionId: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch {
    throw new Error("重置会话失败，请稍后再试。");
  }
}

/**
 * 获取已生成图片列表
 */
export async function fetchGallery(): Promise<GalleryImage[]> {
  const res = await fetch(`${API_BASE}/api/gallery`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`获取图库失败 (${res.status})`);
  return await res.json();
}

export interface GalleryImage {
  filename: string;
  url: string;
  size: number;
  created_at: number;
}

// ============ 会话管理 ============

export interface SessionInfo {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: string | null;
}

export interface SessionListResponse {
  sessions: SessionInfo[];
}

export interface SessionDetail {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: any[];
}

export async function listSessions(): Promise<SessionInfo[]> {
  const res = await fetch(`${API_BASE}/api/sessions`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`获取会话列表失败 (${res.status})`);
  const data = (await res.json()) as SessionListResponse;
  return data.sessions;
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`获取会话详情失败 (${res.status})`);
  return await res.json();
}

export async function createSession(): Promise<{ session_id: string; title: string }> {
  const res = await fetch(`${API_BASE}/api/sessions/new`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`新建会话失败 (${res.status})`);
  return await res.json();
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId, title }),
  });
  if (!res.ok) throw new Error(`重命名失败 (${res.status})`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`删除失败 (${res.status})`);
}

export interface CanvasGenerateRequest {
  prompt: string;
  reference_images?: string[];
  reference_texts?: string[];
  model?: string;
  size?: string;
  preset?: string;
}

export interface CanvasGenerateResponse {
  image_url: string;
  prompt_used: string;
  model_used: string;
}

export async function canvasGenerate(req: CanvasGenerateRequest): Promise<CanvasGenerateResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 600000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/canvas/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("图片生成超时，请稍后重试。");
    }
    throw new Error("无法连接到服务，请确认网络是否正常。");
  }
  clearTimeout(timeoutId);
  if (!res.ok) {
    let errMsg = `生成失败 (${res.status})`;
    try {
      const errData = await res.json();
      errMsg = errData.detail || errMsg;
    } catch {}
    throw new Error(errMsg);
  }
  return (await res.json()) as CanvasGenerateResponse;
}

// ============ 异步生图（submit + poll）============

export interface CanvasSubmitRequest {
  prompt: string;
  reference_images?: string[];
  reference_texts?: string[];
  model?: string;
  size?: string;
  preset?: string;
}

export interface CanvasSubmitResponse {
  task_id: string;
  status: string;
}

export interface CanvasTaskStatus {
  task_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  stage: string; // submitting | queued | generating | downloading | done
  image_url: string;
  error: string;
  error_kind: string;
  error_suggestion: string;
  prompt_used: string;
  model_used: string;
  created_at: number;
}

export async function canvasSubmit(req: CanvasSubmitRequest): Promise<CanvasSubmitResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/canvas/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(req),
    });
  } catch {
    throw new Error("无法连接到服务，请确认网络是否正常。");
  }
  if (!res.ok) {
    let errMsg = `提交失败 (${res.status})`;
    try { const errData = await res.json(); errMsg = errData.detail || errMsg; } catch {}
    throw new Error(errMsg);
  }
  return await res.json();
}

export async function canvasStatus(taskId: string): Promise<CanvasTaskStatus> {
  const res = await fetch(`${API_BASE}/api/canvas/status/${taskId}`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    let errMsg = `查询状态失败 (${res.status})`;
    try { const errData = await res.json(); errMsg = errData.detail || errMsg; } catch {}
    throw new Error(errMsg);
  }
  return await res.json();
}

export interface CanvasPresetsResponse {
  presets: Record<string, string>;
  categories: Array<{ id: string; name: string; presets: string[] }>;
}

export async function getCanvasPresets(): Promise<CanvasPresetsResponse> {
  const res = await fetch(`${API_BASE}/api/canvas/presets`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`获取预设失败 (${res.status})`);
  return await res.json();
}

export interface CanvasInfo {
  canvas_id: string;
  name: string;
  owner: string;
  thumbnail_url: string;
  created_at: string;
  updated_at: string;
  node_count: number;
  connection_count: number;
}

export interface CanvasDetail extends CanvasInfo {
  nodes: any[];
  connections: any[];
}

export interface CanvasSaveRequest {
  canvas_id?: string;
  name: string;
  nodes: any[];
  connections: any[];
}

export async function listCanvases(): Promise<CanvasInfo[]> {
  const res = await fetch(`${API_BASE}/api/canvas/list`, { headers: { ...authHeaders() } });
  if (!res.ok) throw new Error(`获取画布列表失败 (${res.status})`);
  return await res.json();
}

export async function saveCanvas(req: CanvasSaveRequest): Promise<CanvasDetail> {
  const res = await fetch(`${API_BASE}/api/canvas/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    let errMsg = `保存失败 (${res.status})`;
    try { const d = await res.json(); errMsg = d.detail || errMsg; } catch {}
    throw new Error(errMsg);
  }
  return await res.json();
}

export async function loadCanvas(canvasId: string): Promise<CanvasDetail> {
  const res = await fetch(`${API_BASE}/api/canvas/load/${canvasId}`, { headers: { ...authHeaders() } });
  if (!res.ok) {
    let errMsg = `加载失败 (${res.status})`;
    try { const d = await res.json(); errMsg = d.detail || errMsg; } catch {}
    throw new Error(errMsg);
  }
  return await res.json();
}

export async function deleteCanvas(canvasId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/canvas/${canvasId}`, {
    method: "DELETE",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`删除失败 (${res.status})`);
}

export async function createNewCanvas(): Promise<{ canvas_id: string; name: string }> {
  const res = await fetch(`${API_BASE}/api/canvas/new`, {
    method: "POST",
    headers: { ...authHeaders() },
  });
  if (!res.ok) throw new Error(`新建画布失败 (${res.status})`);
  return await res.json();
}

// ============ 文案生成 ============

export interface CopywritingGenerateRequest {
  product: string;
  copy_type?: string;   // title | selling | xhs | script
  style?: string;
  extra?: string;
  temperature?: number;
}

export interface CopywritingGenerateResponse {
  content: string;
  model_used: string;
  copy_type: string;
  style: string;
}

export async function generateCopywriting(req: CopywritingGenerateRequest): Promise<CopywritingGenerateResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 60000);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/copywriting/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error("文案生成超时，请稍后重试。");
    }
    throw new Error("无法连接到服务，请确认网络是否正常。");
  }
  clearTimeout(timeoutId);
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("登录已过期，请重新登录");
  }
  if (!res.ok) {
    let errMsg = `生成失败 (${res.status})`;
    try {
      const errData = await res.json();
      errMsg = errData.detail || errMsg;
    } catch {}
    throw new Error(errMsg);
  }
  return (await res.json()) as CopywritingGenerateResponse;
}
