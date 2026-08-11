import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  RefreshCw,
  Pencil,
  Image as ImageIcon,
  FileText,
  Video,
  Download,
  X,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Plus,
} from "lucide-react";
import type { Artifact } from "@/types";

interface Props {
  artifacts: Artifact[];
  accepted: boolean;
  onAccept: () => void;
  onModify: () => void;
  onRedo: () => void;
  onNewTask: () => void;
}

function shortId(id: string): string {
  const m = id.match(/(?:task-|exec-)?(\d+)/);
  if (m) return `#${m[1]}`;
  return id.length > 10 ? id.slice(-8) : id;
}

function isRealImage(a: Artifact): boolean {
  return a.kind === "IMAGE" && !!a.url_or_path && !a.url_or_path.startsWith("mock://");
}

function ArtifactTile({
  artifact,
  index,
  onPreview,
}: {
  artifact: Artifact;
  index: number;
  onPreview: (a: Artifact) => void;
}) {
  const Icon =
    artifact.kind === "IMAGE"
      ? ImageIcon
      : artifact.kind === "VIDEO"
      ? Video
      : FileText;

  const real = isRealImage(artifact);
  const imageType = artifact.metadata?.image_type as string | undefined;

  const typeLabels: Record<string, string> = {
    main: "主图",
    detail: "详情图",
    scene: "场景图",
    poster: "海报",
    carousel: "轮播图",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index, type: "spring", stiffness: 200, damping: 20 }}
      whileHover={{ scale: 1.03 }}
      className={`group relative aspect-square rounded-xl overflow-hidden border border-gold-500/30 ${real ? "cursor-pointer" : ""} bg-gradient-to-br from-brown-700 via-charcoal-800 to-brown-800`}
      onClick={() => real && onPreview(artifact)}
    >
      {real ? (
        <>
          <img
            src={artifact.url_or_path!}
            alt={`Generated ${typeLabels[imageType || "main"] || "image"} ${index + 1}`}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
          {/* 常驻右下角放大图标 */}
          <div className="absolute bottom-1.5 right-1.5 w-6 h-6 rounded-full bg-black/50 backdrop-blur flex items-center justify-center z-10 opacity-80">
            <ZoomIn className="w-3.5 h-3.5 text-white" />
          </div>
          {/* hover 遮罩提示 */}
          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition" />
        </>
      ) : (
        <>
          <div
            className="absolute inset-0 opacity-30 group-hover:opacity-50 transition"
            style={{
              background:
                "radial-gradient(circle at 30% 30%, rgba(37, 99, 235,0.4), transparent 60%)",
            }}
          />
          <div className="relative h-full flex flex-col items-center justify-center gap-2">
            <Icon className="w-7 h-7 text-gold-400" />
            <div className="text-[10px] text-ivory-400/60 font-mono">
              #{shortId(artifact.artifact_id)}
            </div>
            <div className="text-[10px] text-gold-300/80 tracking-wider">
              {artifact.kind}
            </div>
          </div>
        </>
      )}
      {imageType && (
        <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/50 backdrop-blur text-[9px] text-gold-300 z-10">
          {typeLabels[imageType] || imageType}
        </div>
      )}
    </motion.div>
  );
}

export default function Gallery({
  artifacts,
  accepted,
  onAccept,
  onModify,
  onRedo,
  onNewTask,
}: Props) {
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const imgRef = useRef<HTMLImageElement>(null);
  const realImgs = artifacts.filter(isRealImage);
  const realImgIndices = artifacts
    .map((a, i) => (isRealImage(a) ? i : -1))
    .filter((i) => i >= 0);

  const preview = previewIndex !== null ? artifacts[previewIndex] : null;

  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const openPreview = (a: Artifact) => {
    const idx = artifacts.findIndex((x) => x.artifact_id === a.artifact_id);
    setPreviewIndex(idx);
    resetZoom();
  };

  const closePreview = () => {
    setPreviewIndex(null);
    resetZoom();
  };

  const goPrev = () => {
    if (previewIndex === null) return;
    const realIdx = realImgIndices.indexOf(previewIndex);
    const prevRealIdx = (realIdx - 1 + realImgIndices.length) % realImgIndices.length;
    setPreviewIndex(realImgIndices[prevRealIdx]);
    resetZoom();
  };

  const goNext = () => {
    if (previewIndex === null) return;
    const realIdx = realImgIndices.indexOf(previewIndex);
    const nextRealIdx = (realIdx + 1) % realImgIndices.length;
    setPreviewIndex(realImgIndices[nextRealIdx]);
    resetZoom();
  };

  const zoomIn = () => setScale((s) => Math.min(s * 1.3, 5));
  const zoomOut = () => setScale((s) => Math.max(s / 1.3, 0.5));

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) {
      zoomIn();
    } else {
      zoomOut();
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (scale <= 1) return;
    e.preventDefault();
    setIsDragging(true);
    dragStart.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  };

  const handleMouseUp = () => setIsDragging(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (previewIndex === null) return;
      if (e.key === "Escape") closePreview();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "+" || e.key === "=") zoomIn();
      if (e.key === "-") zoomOut();
      if (e.key === "0") resetZoom();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [previewIndex, realImgIndices]);

  return (
    <>
      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 40 }}
        transition={{ type: "spring", stiffness: 240, damping: 22 }}
        className="bg-brown-800/70 backdrop-blur border border-gold-500/20 rounded-2xl overflow-hidden shadow-warm-glow"
      >
        <div className="h-1 bg-gradient-to-r from-gold-600 via-gold-400 to-terracotta-500" />
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-serif text-xl text-gold-300">产出物</h3>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-gold-500/15 text-gold-300 border border-gold-500/30 tracking-wider">
              {artifacts.length} 件
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-4">
            {artifacts.map((a, i) => (
              <ArtifactTile key={a.artifact_id} artifact={a} index={i} onPreview={openPreview} />
            ))}
          </div>

          {!accepted ? (
            <div className="flex flex-col gap-2">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onAccept}
                className="w-full py-2.5 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-1.5"
              >
                <Check className="w-4 h-4" /> 可以了，验收
              </motion.button>
              <div className="flex gap-2">
                <button
                  onClick={onModify}
                  className="flex-1 py-2 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-xs transition flex items-center justify-center gap-1.5"
                >
                  <Pencil className="w-3 h-3" /> 改第 N 张
                </button>
                <button
                  onClick={onRedo}
                  className="flex-1 py-2 rounded-full border border-terracotta-500/40 text-terracotta-300 hover:bg-terracotta-500/10 text-xs transition flex items-center justify-center gap-1.5"
                >
                  <RefreshCw className="w-3 h-3" /> 重做
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <div className="text-center py-3 rounded-full bg-gold-500/10 border border-gold-500/30 text-gold-300 text-sm">
                ✓ 已验收归档
              </div>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onNewTask}
                className="w-full py-2.5 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-1.5"
              >
                <Plus className="w-4 h-4" /> 开始新任务
              </motion.button>
            </div>
          )}
        </div>
      </motion.div>

      {/* 大图预览 - 增强版 */}
      <AnimatePresence>
        {preview && isRealImage(preview) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closePreview}
            className="fixed inset-0 z-[60] bg-charcoal-900/98 backdrop-blur-md flex items-center justify-center"
            onWheel={handleWheel}
          >
            {/* 顶部工具栏 */}
            <div
              className="absolute top-4 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-charcoal-800/90 border border-gold-500/20 rounded-full px-2 py-1.5 backdrop-blur z-20"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={zoomOut}
                className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                title="缩小 (-)"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs text-ivory-400 w-12 text-center font-mono">
                {Math.round(scale * 100)}%
              </span>
              <button
                onClick={zoomIn}
                className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                title="放大 (+)"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <div className="w-px h-5 bg-gold-500/20 mx-1" />
              <button
                onClick={resetZoom}
                className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                title="重置 (0)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <div className="w-px h-5 bg-gold-500/20 mx-1" />
              <a
                href={preview.url_or_path!}
                download
                onClick={(e) => e.stopPropagation()}
                className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                title="下载原图"
              >
                <Download className="w-4 h-4" />
              </a>
            </div>

            {/* 图片计数器 */}
            {realImgIndices.length > 1 && (
              <div className="absolute top-4 right-4 bg-charcoal-800/90 border border-gold-500/20 rounded-full px-3 py-1.5 text-xs text-ivory-400 backdrop-blur z-20">
                {realImgIndices.indexOf(previewIndex!) + 1} / {realImgIndices.length}
              </div>
            )}

            {/* 左右翻页按钮 */}
            {realImgIndices.length > 1 && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); goPrev(); }}
                  className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-charcoal-800/80 border border-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 hover:bg-charcoal-700 transition z-20 backdrop-blur"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); goNext(); }}
                  className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-charcoal-800/80 border border-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 hover:bg-charcoal-700 transition z-20 backdrop-blur"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </>
            )}

            {/* 关闭按钮 */}
            <button
              onClick={(e) => { e.stopPropagation(); closePreview(); }}
              className="absolute top-4 left-4 w-9 h-9 rounded-full bg-charcoal-800/90 border border-gold-500/20 flex items-center justify-center text-ivory-400 hover:text-gold-300 transition z-20 backdrop-blur"
            >
              <X className="w-5 h-5" />
            </button>

            {/* 图片 — 点击图片本身不关闭，点击图片外的蒙层区域关闭 */}
            <motion.img
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              ref={imgRef}
              src={preview.url_or_path!}
              alt="产出物预览"
              draggable={false}
              className="max-w-[90vw] max-h-[85vh] object-contain select-none rounded-lg shadow-2xl z-10"
              onClick={(e) => e.stopPropagation()}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              style={{
                cursor: scale > 1 ? (isDragging ? "grabbing" : "grab") : "default",
                transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                transition: isDragging ? "none" : "transform 0.2s ease-out",
              }}
            />

            {/* 底部提示 */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[11px] text-ivory-500/60 bg-charcoal-800/70 rounded-full px-3 py-1 backdrop-blur">
              滚轮缩放 · 拖拽移动 · ← → 翻页 · ESC 关闭
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
