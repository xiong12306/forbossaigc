import { create } from "zustand";
import {
  chat as apiChat,
  reset as apiReset,
  uploadImage as apiUpload,
  listSessions,
  getSession,
  createSession,
  deleteSession,
  renameSession,
  type SessionInfo,
} from "@/api";
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
  sessions: SessionInfo[];
  sessionsLoading: boolean;
  activeSessionId: string | null;
  sendMessage: (text: string, opts?: { hidePanel?: boolean; images?: string[] }) => Promise<void>;
  uploadImage: (file: File) => Promise<string>;
  resetSession: () => Promise<void>;
  loadSessions: () => Promise<void>;
  switchSession: (sessionId: string) => Promise<void>;
  startNewSession: () => Promise<void>;
  deleteChat: (sessionId: string) => Promise<void>;
  renameChat: (sessionId: string, title: string) => Promise<void>;
}

let msgCounter = 0;
function nextId(): string {
  msgCounter += 1;
  return `m_${Date.now()}_${msgCounter}`;
}

function serverMsgToChatMessage(m: any, idx: number): ChatMessage {
  const role = m.role === "boss" ? "boss" : "assistant";
  return {
    id: `hist_${idx}_${Date.now()}`,
    role,
    text: m.text || "",
    images: m.images || undefined,
    artifacts: m.artifacts || null,
    summary: m.summary || null,
    followUp: m.followUp || undefined,
    speakText: m.speakText,
  };
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
  sessions: [],
  sessionsLoading: false,
  activeSessionId: null,

  sendMessage: async (text: string, opts?: { hidePanel?: boolean; images?: string[] }) => {
    const trimmed = text.trim();
    if (!trimmed || get().loading) return;

    let sid = get().sessionId;
    if (!sid) {
      const newSess = await createSession();
      sid = newSess.session_id;
      set({ sessionId: sid, activeSessionId: sid });
    }

    const bossMsg: ChatMessage = { id: nextId(), role: "boss", text: trimmed, images: opts?.images };

    const hideNow = opts?.hidePanel || /^(确认|开始|重做|生成)/.test(trimmed);
    set((s) => ({
      messages: [...s.messages, bossMsg],
      loading: true,
      error: null,
      ...(hideNow ? { currentSummary: null, currentArtifacts: null } : {}),
    }));

    try {
      const res = await apiChat(trimmed, sid, opts?.images);
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
      // 刷新会话列表（标题/时间更新）
      get().loadSessions();
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

  uploadImage: async (file: File) => {
    return apiUpload(file);
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
      activeSessionId: null,
    });
  },

  loadSessions: async () => {
    set({ sessionsLoading: true });
    try {
      const list = await listSessions();
      set({ sessions: list, sessionsLoading: false });
    } catch {
      set({ sessionsLoading: false });
    }
  },

  switchSession: async (sessionId: string) => {
    if (get().loading) return;
    try {
      const detail = await getSession(sessionId);
      const msgs = detail.messages.map((m, i) => serverMsgToChatMessage(m, i));
      set({
        messages: msgs,
        sessionId,
        activeSessionId: sessionId,
        currentStatus: msgs.length > 0 ? "accepted" : null,
        currentSummary: null,
        currentArtifacts: null,
        timeline: [],
        loading: false,
        error: null,
      });
    } catch (e) {
      console.error("切换会话失败:", e);
    }
  },

  startNewSession: async () => {
    if (get().loading) return;
    set({
      messages: [],
      sessionId: null,
      activeSessionId: null,
      currentStatus: null,
      currentSummary: null,
      currentArtifacts: null,
      timeline: [],
      loading: false,
      error: null,
    });
  },

  deleteChat: async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      const { activeSessionId } = get();
      if (activeSessionId === sessionId) {
        set({
          messages: [],
          sessionId: null,
          activeSessionId: null,
          currentStatus: null,
          currentSummary: null,
          currentArtifacts: null,
          timeline: [],
        });
      }
      await get().loadSessions();
    } catch (e) {
      console.error("删除会话失败:", e);
    }
  },

  renameChat: async (sessionId: string, title: string) => {
    try {
      await renameSession(sessionId, title);
      set((s) => ({
        sessions: s.sessions.map((sess) =>
          sess.session_id === sessionId ? { ...sess, title } : sess
        ),
      }));
    } catch (e) {
      console.error("重命名失败:", e);
    }
  },
}));
