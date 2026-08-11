import { useEffect, useRef, useCallback, useState } from "react";
import { motion } from "framer-motion";
import BrandBar from "@/components/BrandBar";
import Timeline from "@/components/Timeline";
import ChatStream from "@/components/ChatStream";
import SidePanel from "@/components/SidePanel";
import BrandOnboarding from "@/components/BrandOnboarding";
import GalleryDrawer from "@/components/GalleryDrawer";
import SessionSidebar from "@/components/SessionSidebar";
import { useChat } from "@/hooks/useChat";
import { useSpeech } from "@/hooks/useSpeech";
import { Menu, X } from "lucide-react";
import type { SelectedTypes } from "@/components/ImageTypeSelector";

/**
 * 主页面：
 * 桌面端：左栏(会话列表260px) + 中栏(聊天流flex-1) + 右栏(上下文360px)
 * 移动端：汉堡菜单 → 侧边抽屉
 */
export default function Home() {
  const {
    messages,
    timeline,
    loading,
    currentStatus,
    currentSummary,
    currentArtifacts,
    sendMessage,
    uploadImage,
    resetSession,
    loadSessions,
    activeSessionId,
    startNewSession,
  } = useChat();

  const inputRef = useRef<HTMLInputElement>(null);
  const { speak } = useSpeech();
  const [galleryOpen, setGalleryOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // 首次加载：获取会话列表
  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // 监听最新助手消息，触发 TTS 播报
  const lastMsg = messages[messages.length - 1];
  const lastSpeakText = lastMsg?.role === "assistant" ? lastMsg.speakText : undefined;
  useEffect(() => {
    if (lastSpeakText) speak(lastSpeakText);
  }, [lastSpeakText, speak]);

  const handleModify = useCallback(() => inputRef.current?.focus(), []);

  const handleConfirmWithSelection = useCallback(
    async (selectedTypes?: SelectedTypes) => {
      const defaultType = (currentSummary?.params.image_type as string) || "main";
      const defaultQty = (currentSummary?.params.quantity as number) || 1;

      let msg = "确认";
      if (selectedTypes && Object.keys(selectedTypes).length > 0) {
        const entries = Object.entries(selectedTypes);
        const [selectedType, selectedQty] = entries[0];
        const typeNames: Record<string, string> = {
          main: "商品主图",
          detail: "产品详情图",
          scene: "场景图",
          poster: "营销海报",
          carousel: "轮播图",
        };
        const needModifyType = selectedType !== defaultType;
        const needModifyQty = selectedQty !== defaultQty;
        const parts: string[] = [];
        if (needModifyType) parts.push(`类型改成${typeNames[selectedType] || selectedType}`);
        if (needModifyQty) parts.push(`数量改成${selectedQty}张`);
        if (parts.length > 0) msg = `${parts.join("，")}，确认`;
      }
      await sendMessage(msg, { hidePanel: true });
    },
    [sendMessage, currentSummary]
  );

  const handleNewChat = async () => {
    await startNewSession();
    setSidebarOpen(false);
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      <BrandBar
        onReset={resetSession}
        onOpenGallery={() => setGalleryOpen(true)}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
      />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="flex-1 flex flex-col lg:flex-row overflow-hidden relative"
      >
        {/* 桌面端：会话列表侧栏 */}
        <aside className="hidden lg:flex lg:w-[260px] flex-shrink-0 border-r border-brown-700/50 bg-charcoal-850/50 flex-col">
          <SessionSidebar />
          {/* 底部时间线（精简） */}
          <div className="border-t border-brown-700/50 p-2">
            <Timeline timeline={timeline} />
          </div>
        </aside>

        {/* 移动端：会话抽屉 */}
        {sidebarOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 bg-black/50 z-40 lg:hidden"
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25 }}
              className="fixed left-0 top-0 bottom-0 w-[260px] z-50 lg:hidden bg-charcoal-850 border-r border-brown-700/50 flex flex-col pt-14"
            >
              <SessionSidebar onClose={() => setSidebarOpen(false)} />
              <div className="border-t border-brown-700/50 p-2">
                <Timeline timeline={timeline} />
              </div>
            </motion.aside>
          </>
        )}

        {/* 中栏：聊天流（主） */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* 空状态时显示提示 */}
          {messages.length === 0 && !activeSessionId && (
            <div className="flex items-center justify-center px-6 pt-4">
              <button
                onClick={handleNewChat}
                className="text-gold-400 hover:text-gold-300 text-sm underline underline-offset-4"
              >
                开始新对话 →
              </button>
            </div>
          )}
          <ChatStream
            messages={messages}
            loading={loading}
            onSend={(text, images) => sendMessage(text, images ? { images } : undefined)}
            onUpload={uploadImage}
            inputRef={inputRef}
          />
        </main>

        {/* 右栏：上下文卡片 */}
        <aside className="lg:w-[360px] lg:flex-shrink-0 border-t lg:border-t-0 lg:border-l border-brown-700/50 bg-charcoal-800/40 lg:overflow-y-auto p-4 max-h-[40vh] lg:max-h-none">
          <SidePanel
            status={currentStatus}
            summary={currentSummary}
            artifacts={currentArtifacts}
            onConfirm={handleConfirmWithSelection}
            onModify={handleModify}
            onCancel={() => sendMessage("取消", { hidePanel: true })}
            onAccept={() => sendMessage("可以了")}
            onRedo={() => sendMessage("重做", { hidePanel: true })}
            onNewTask={startNewSession}
          />
        </aside>
      </motion.div>

      {/* 移动端底部水平时间线 */}
      <div className="md:hidden border-t border-brown-700/50 bg-charcoal-800/60 px-2 py-1.5">
        <Timeline timeline={timeline} horizontal />
      </div>

      <BrandOnboarding />

      <GalleryDrawer open={galleryOpen} onClose={() => setGalleryOpen(false)} />
    </div>
  );
}
