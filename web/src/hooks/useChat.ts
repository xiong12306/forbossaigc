import { create } from "zustand";
import { chat as apiChat, reset as apiReset } from "@/api";
import type {
  ChatMessage,
  ChatStatus,
  Summary,
  Artifact,
  TimelineNode,
} from "@/types";

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  currentStatus: ChatStatus | null;
  currentSummary: Summary | null;
  currentArtifacts: Artifact[] | null;
  timeline: TimelineNode[];
  loading: boolean;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  resetSession: () => Promise<void>;
}

// 生成前端消息唯一 id
let msgCounter = 0;
function nextId(): string {
  msgCounter += 1;
  return `m_${Date.now()}_${msgCounter}`;
}

export const useChat = create<ChatState>((set, get) => ({
  messages: [],
  sessionId: null,
  currentStatus: null,
  currentSummary: null,
  currentArtifacts: null,
  timeline: [],
  loading: false,
  error: null,

  sendMessage: async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || get().loading) return;

    // 先把老板消息加入列表
    const bossMsg: ChatMessage = { id: nextId(), role: "boss", text: trimmed };
    set((s) => ({
      messages: [...s.messages, bossMsg],
      loading: true,
      error: null,
    }));

    try {
      const res = await apiChat(trimmed, get().sessionId ?? undefined);
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        text: res.message,
        summary: res.summary ?? null,
        artifacts: res.artifacts ?? null,
        followUp: res.follow_up_question,
        speakText: res.speak_text,
      };
      set((s) => ({
        messages: [...s.messages, assistantMsg],
        sessionId: res.session_id,
        currentStatus: res.status,
        currentSummary: res.summary ?? null,
        currentArtifacts: res.artifacts ?? null,
        timeline: res.timeline ?? s.timeline,
        loading: false,
      }));
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : "未知错误";
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        text: `⚠️ ${errMsg}`,
      };
      set((s) => ({
        messages: [...s.messages, assistantMsg],
        loading: false,
        error: errMsg,
      }));
    }
  },

  resetSession: async () => {
    const sid = get().sessionId;
    if (sid) {
      try {
        await apiReset(sid);
      } catch {
        // 重置失败不阻塞前端清空
      }
    }
    set({
      messages: [],
      sessionId: null,
      currentStatus: null,
      currentSummary: null,
      currentArtifacts: null,
      timeline: [],
      loading: false,
      error: null,
    });
  },
}));
