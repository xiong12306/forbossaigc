import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ZoomIn, Download } from "lucide-react";
import type { ChatMessage, Artifact } from "@/types";
import ImageLightbox, { type LightboxImage } from "./ImageLightbox";

interface Props {
  message: ChatMessage;
}

const TYPE_LABELS: Record<string, string> = {
  main: "主图",
  detail: "详情图",
  scene: "场景图",
  poster: "海报",
  carousel: "轮播图",
};

function isRealImage(a: Artifact): boolean {
  return a.kind === "IMAGE" && !!a.url_or_path && !a.url_or_path.startsWith("mock://");
}

/**
 * 单条消息气泡：老板右对齐暖象牙底，助手左对齐深褐底琥珀金描边
 * 助手消息携带 artifacts 时，在气泡下方渲染大图卡片网格
 */
export default function MessageBubble({ message }: Props) {
  const isBoss = message.role === "boss";
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const realArtifacts = (message.artifacts ?? []).filter(isRealImage);
  const lightboxImages: LightboxImage[] = realArtifacts.map((a) => ({
    url: a.url_or_path!,
    label: TYPE_LABELS[(a.metadata?.image_type as string) || "main"] || "生成图片",
  }));

  const handleDownload = async (url: string, idx: number) => {
    try {
      const res = await fetch(url);
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = `image_${idx + 1}.png`;
      a.click();
      URL.revokeObjectURL(u);
    } catch {
      window.open(url, "_blank");
    }
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0, x: isBoss ? 20 : -20, y: 6 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        transition={{ type: "spring", stiffness: 280, damping: 24 }}
        className={`flex ${isBoss ? "justify-end" : "justify-start"}`}
      >
        <div
          className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
            isBoss
              ? "bg-ivory-400 text-brown-900 rounded-br-md"
              : "bg-brown-800/80 text-ivory-500 border border-gold-500/30 rounded-bl-md"
          }`}
        >
          {/* 老板上传的参考图 */}
          {message.images && message.images.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-2">
              {message.images.map((url, idx) => (
                <img
                  key={idx}
                  src={url}
                  alt={`参考图${idx + 1}`}
                  className="max-w-[200px] max-h-[200px] rounded-lg object-cover"
                />
              ))}
            </div>
          )}
          {message.text}
          {message.followUp && (
            <div className="mt-2 pt-2 border-t border-gold-500/20 text-gold-300 text-xs">
              {message.followUp}
            </div>
          )}
        </div>
      </motion.div>

      {/* 助手消息的生成结果：大图卡片网格 */}
      {!isBoss && realArtifacts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, type: "spring", stiffness: 200, damping: 22 }}
          className="flex justify-start w-full"
        >
          <div className="w-full max-w-[600px]">
            <div className={`grid gap-3 ${realArtifacts.length === 1 ? "grid-cols-1" : "grid-cols-2"}`}>
              {realArtifacts.map((art, idx) => {
                const imageType = art.metadata?.image_type as string | undefined;
                const label = TYPE_LABELS[imageType || "main"] || "生成图片";
                return (
                  <motion.div
                    key={art.artifact_id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 * idx + 0.2 }}
                    whileHover={{ scale: 1.02 }}
                    className="group relative rounded-xl overflow-hidden border border-gold-500/30 bg-brown-800/60 cursor-pointer shadow-lg"
                    onClick={() => setLightboxIndex(idx)}
                  >
                    <img
                      src={art.url_or_path!}
                      alt={`${label} ${idx + 1}`}
                      className="w-full h-full object-cover max-h-[400px]"
                      loading="lazy"
                    />
                    {/* 类型标签 */}
                    <div className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur text-[10px] text-gold-300 border border-gold-500/20">
                      {label}
                    </div>
                    {/* 操作按钮 */}
                    <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition">
                      <button
                        onClick={(e) => { e.stopPropagation(); setLightboxIndex(idx); }}
                        className="w-7 h-7 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-white hover:bg-gold-500/40 transition"
                        title="查看大图"
                      >
                        <ZoomIn className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDownload(art.url_or_path!, idx); }}
                        className="w-7 h-7 rounded-full bg-black/60 backdrop-blur flex items-center justify-center text-white hover:bg-gold-500/40 transition"
                        title="下载"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    {/* 底部渐变遮罩 */}
                    <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-black/40 to-transparent pointer-events-none" />
                  </motion.div>
                );
              })}
            </div>
          </div>
        </motion.div>
      )}

      {/* 全屏查看 */}
      <AnimatePresence>
        {lightboxIndex !== null && lightboxImages.length > 0 && (
          <ImageLightbox
            images={lightboxImages}
            index={lightboxIndex}
            onClose={() => setLightboxIndex(null)}
            onIndexChange={setLightboxIndex}
          />
        )}
      </AnimatePresence>
    </>
  );
}
