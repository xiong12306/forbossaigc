import { useEffect, useRef, useCallback, useState } from "react";
import { motion } from "framer-motion";
import BrandBar from "@/components/BrandBar";
import Timeline from "@/components/Timeline";
import ChatStream from "@/components/ChatStream";
import SidePanel from "@/components/SidePanel";
import BrandOnboarding from "@/components/BrandOnboarding";
import GalleryDrawer from "@/components/GalleryDrawer";
import { useChat } from "@/hooks/useChat";
import { useSpeech } from "@/hooks/useSpeech";
import type { SelectedTypes } from "@/components/ImageTypeSelector";

/**
 * 主页面：单页三栏布局
 * 左栏（窄，约 200px）状态时间线 + 中栏（flex-1）聊天流 + 右栏（约 360px）上下文卡片
 * 响应式：平板折叠左栏到顶部水平时间线，移动端单列
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
  } = useChat();

  const inputRef = useRef<HTMLInputElement>(null);
  const { speak } = useSpeech();
  const [galleryOpen, setGalleryOpen] = useState(false);

  // 监听最新助手消息，触发 TTS 播报（拟人化语音回复）
  const lastMsg = messages[messages.length - 1];
  const lastSpeakText = lastMsg?.role === "assistant" ? lastMsg.speakText : undefined;
  useEffect(() => {
    if (lastSpeakText) speak(lastSpeakText);
  }, [lastSpeakText, speak]);

  // 修改按钮：聚焦输入框，让老板用文字描述调整
  const handleModify = useCallback(() => inputRef.current?.focus(), []);

  // 带图片类型选择的确认：根据用户选择调整参数后确认
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

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      <BrandBar onReset={resetSession} onOpenGallery={() => setGalleryOpen(true)} />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="flex-1 flex flex-col lg:flex-row overflow-hidden"
      >
        {/* 左栏：时间线（桌面垂直） */}
        <aside className="hidden md:block md:w-[200px] flex-shrink-0 border-r border-brown-700/50 bg-charcoal-800/40 overflow-y-auto">
          <Timeline timeline={timeline} />
        </aside>

        {/* 中栏：聊天流（主） */}
        <main className="flex-1 flex flex-col min-w-0">
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
            onNewTask={resetSession}
          />
        </aside>
      </motion.div>

      {/* 平板/移动端顶部水平时间线（md 以下显示在底部条带） */}
      <div className="md:hidden border-t border-brown-700/50 bg-charcoal-800/60 px-2 py-1.5">
        <Timeline timeline={timeline} horizontal />
      </div>

      <BrandOnboarding />

      {/* 图库抽屉 */}
      <GalleryDrawer open={galleryOpen} onClose={() => setGalleryOpen(false)} />
    </div>
  );
}
