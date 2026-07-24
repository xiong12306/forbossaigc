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
  summary?: Summary | null;
  artifacts?: Artifact[] | null;
  followUp?: string;
  speakText?: string; // 助手回复的 TTS 播报文本
}
