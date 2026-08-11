import { useState } from "react";
import { motion } from "framer-motion";
import { Plus, MessageSquare, Trash2, Edit3, Check, X } from "lucide-react";
import { useChat } from "@/hooks/useChat";

interface Props {
  onClose?: () => void;
}

/**
 * 左侧对话列表：新建对话、切换对话、重命名、删除
 */
export default function SessionSidebar({ onClose }: Props) {
  const {
    sessions,
    activeSessionId,
    sessionsLoading,
    switchSession,
    startNewSession,
    deleteChat,
    renameChat,
  } = useChat();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const handleSwitch = (sid: string) => {
    if (sid === activeSessionId) return;
    switchSession(sid);
    onClose?.();
  };

  const handleNewChat = async () => {
    await startNewSession();
    onClose?.();
  };

  const startRename = (sid: string, currentTitle: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(sid);
    setEditTitle(currentTitle);
  };

  const confirmRename = async (sid: string) => {
    const title = editTitle.trim();
    if (title) {
      await renameChat(sid, title);
    }
    setEditingId(null);
  };

  const handleDelete = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("确定删除这个对话吗？")) {
      await deleteChat(sid);
    }
  };

  return (
    <div className="flex flex-col h-full bg-charcoal-850/80 backdrop-blur-sm">
      {/* 顶部新建按钮 */}
      <div className="p-3 border-b border-brown-700/50">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-gold-500/30 text-gold-300 hover:bg-gold-500/10 hover:border-gold-500/50 transition text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          新建对话
        </motion.button>
      </div>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessionsLoading && sessions.length === 0 && (
          <div className="text-center py-8 text-ivory-400/40 text-xs">加载中…</div>
        )}
        {!sessionsLoading && sessions.length === 0 && (
          <div className="text-center py-8 text-ivory-400/40 text-xs">暂无对话记录</div>
        )}
        {sessions.map((sess) => {
          const isActive = sess.session_id === activeSessionId;
          const isEditing = editingId === sess.session_id;
          return (
            <motion.div
              key={sess.session_id}
              layout
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              onClick={() => !isEditing && handleSwitch(sess.session_id)}
              className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition ${
                isActive
                  ? "bg-gold-500/15 border border-gold-500/30"
                  : "hover:bg-brown-800/60 border border-transparent"
              }`}
            >
              {isEditing ? (
                <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") confirmRename(sess.session_id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    className="flex-1 bg-brown-900/60 border border-gold-500/30 rounded px-2 py-1 text-sm text-ivory-300 outline-none focus:border-gold-500/50"
                    maxLength={30}
                  />
                  <button
                    onClick={() => confirmRename(sess.session_id)}
                    className="w-6 h-6 rounded hover:bg-gold-500/20 flex items-center justify-center text-gold-400"
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="w-6 h-6 rounded hover:bg-red-500/20 flex items-center justify-center text-red-400"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <MessageSquare className={`w-4 h-4 flex-shrink-0 ${isActive ? "text-gold-400" : "text-ivory-400/50"}`} />
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm truncate ${isActive ? "text-gold-300" : "text-ivory-300"}`}>
                      {sess.title}
                    </div>
                    {sess.last_message && (
                      <div className="text-[11px] text-ivory-400/40 truncate mt-0.5">
                        {sess.last_message}
                      </div>
                    )}
                  </div>
                  {/* 操作按钮 */}
                  <div className={`flex gap-0.5 items-center ${isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"} transition`}>
                    <button
                      onClick={(e) => startRename(sess.session_id, sess.title, e)}
                      className="w-6 h-6 rounded hover:bg-brown-700/80 flex items-center justify-center text-ivory-400/60 hover:text-gold-300 transition"
                      title="重命名"
                    >
                      <Edit3 className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => handleDelete(sess.session_id, e)}
                      className="w-6 h-6 rounded hover:bg-red-500/20 flex items-center justify-center text-ivory-400/60 hover:text-red-400 transition"
                      title="删除"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
