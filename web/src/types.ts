// 与后端 API 契约一致的类型定义

export type ChatStatus =
  | "pending"
  | "understanding"
  | "awaiting_confirmation"
  | "confirmed"
  | "executing"
  | "delivered"
  | "accepted"
  | "cancelled"
  | "failed";

export interface ChatRequest {
  message: string;
  session_id?: string;
  images?: string[]; // 老板上传的参考图 URL 列表
}

export interface Summary {
  task_type: string;
  product: string | null;
  params: Record<string, unknown>;
  platform: string;
  estimated_duration_sec: number;
  estimated_cost: number;
  is_high_cost: boolean;
}

export interface Artifact {
  artifact_id: string;
  kind: "IMAGE" | "VIDEO" | "TEXT";
  url_or_path: string | null;
  thumbnail_path: string | null;
  metadata: Record<string, unknown>;
}

export type TimelineNodeStatus = "done" | "active" | "pending" | "cancelled";

export interface TimelineNode {
  label: string;
  status: TimelineNodeStatus;
}

export interface ChatResponse {
  session_id: string;
  status: ChatStatus;
  message: string;
  speak_text?: string;
  follow_up_question?: string;
  summary?: Summary | null;
  artifacts?: Artifact[] | null;
  timeline: TimelineNode[];
}

// 前端 UI 用的消息结构
export type MessageRole = "boss" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  images?: string[]; // 老板上传的参考图 URL 列表
  summary?: Summary | null;
  artifacts?: Artifact[] | null;
  followUp?: string;
  speakText?: string; // 助手回复的 TTS 播报文本
}

// 会话管理相关类型
export interface SessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message?: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface SessionDetailResponse {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Array<{
    role: "boss" | "assistant";
    text: string;
    images?: string[];
    summary?: Summary | null;
    artifacts?: Artifact[] | null;
    follow_up?: string;
    speak_text?: string;
    created_at?: string;
  }>;
}

export interface SessionCreateResponse {
  session_id: string;
  title: string;
}
