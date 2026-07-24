import type { ChatRequest, ChatResponse } from "@/types";
import { getToken } from "@/lib/auth";

const API_BASE = "";

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * 调用 /api/chat 与助手对话
 * 后端不可用时抛出友好错误
 */
export async function chat(
  message: string,
  sessionId?: string
): Promise<ChatResponse> {
  const body: ChatRequest = { message, session_id: sessionId };
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error("无法连接到 BossAIGC 服务，请确认网络是否正常。");
  }
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
