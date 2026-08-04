import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Download,
  RefreshCw,
  ImageIcon,
  Loader2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { fetchGallery, type GalleryImage } from "@/api";

interface GalleryDrawerProps {
  open: boolean;
  onClose: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function GalleryDrawer({ open, onClose }: GalleryDrawerProps) {
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const preview = previewIndex !== null ? images[previewIndex] : null;

  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const openPreview = (idx: number) => {
    setPreviewIndex(idx);
    resetZoom();
  };

  const closePreview = () => {
    setPreviewIndex(null);
    resetZoom();
  };

  const goPrev = () => {
    if (previewIndex === null || images.length === 0) return;
    setPreviewIndex((previewIndex - 1 + images.length) % images.length);
    resetZoom();
  };

  const goNext = () => {
    if (previewIndex === null || images.length === 0) return;
    setPreviewIndex((previewIndex + 1) % images.length);
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
  }, [previewIndex, images.length]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchGallery();
      setImages(data);
    } catch (e) {
      console.error("加载图库失败:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) load();
  }, [open, load]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-charcoal-900/60 backdrop-blur-sm"
          />
          {/* 抽屉 */}
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-charcoal-900 border-l border-gold-500/20 flex flex-col"
          >
            {/* 头部 */}
            <header className="flex items-center justify-between px-5 py-4 border-b border-brown-700/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center">
                  <ImageIcon className="w-4 h-4 text-charcoal-900" />
                </div>
                <div>
                  <div className="font-serif text-lg text-gold-400">图库</div>
                  <div className="text-[11px] text-ivory-400/50">
                    共 {images.length} 张已生成图片
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={load}
                  disabled={loading}
                  className="p-2 rounded-lg text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/50 transition disabled:opacity-50"
                  title="刷新"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/50 transition"
                  title="关闭"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </header>

            {/* 图片网格 */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
              {loading && images.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20">
                  <Loader2 className="w-8 h-8 text-gold-400 animate-spin mb-3" />
                  <div className="text-sm text-ivory-400/60">加载中...</div>
                </div>
              ) : images.length > 0 ? (
                <div className="grid grid-cols-2 gap-3">
                  {images.map((img, i) => (
                    <motion.div
                      key={img.filename}
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: i * 0.03 }}
                      className="group relative aspect-square rounded-lg overflow-hidden border border-gold-500/15 hover:border-gold-500/40 cursor-pointer transition-all"
                      onClick={() => openPreview(i)}
                    >
                      <img
                        src={img.url}
                        alt={img.filename}
                        loading="lazy"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      {/* 常驻右下角放大图标 */}
                      <div className="absolute bottom-1.5 right-1.5 w-6 h-6 rounded-full bg-black/50 backdrop-blur flex items-center justify-center z-10 opacity-80">
                        <ZoomIn className="w-3.5 h-3.5 text-white" />
                      </div>
                      {/* 底部信息 */}
                      <div className="absolute bottom-0 inset-x-0 p-2 bg-gradient-to-t from-charcoal-900/90 to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="text-[10px] text-ivory-400/70 truncate">
                          {formatTime(img.created_at)}
                        </div>
                        <div className="text-[10px] text-ivory-400/50">
                          {formatSize(img.size)}
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-20">
                  <div className="w-16 h-16 rounded-full bg-brown-800/60 border border-gold-500/20 flex items-center justify-center mb-4">
                    <ImageIcon className="w-8 h-8 text-ivory-400/40" />
                  </div>
                  <div className="font-serif text-lg text-ivory-400/60 mb-1">
                    暂无图片
                  </div>
                  <div className="text-xs text-ivory-400/40">
                    生成过的图片会在这里展示
                  </div>
                </div>
              )}
            </div>
          </motion.aside>

          {/* 大图预览 - 增强版 */}
          <AnimatePresence>
            {preview && (
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
                    href={preview.url}
                    download={preview.filename}
                    onClick={(e) => e.stopPropagation()}
                    className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                    title="下载原图"
                  >
                    <Download className="w-4 h-4" />
                  </a>
                </div>

                {/* 图片计数器 */}
                {images.length > 1 && (
                  <div className="absolute top-4 right-4 bg-charcoal-800/90 border border-gold-500/20 rounded-full px-3 py-1.5 text-xs text-ivory-400 backdrop-blur z-20">
                    {previewIndex! + 1} / {images.length}
                  </div>
                )}

                {/* 图片信息 */}
                <div className="absolute bottom-16 left-1/2 -translate-x-1/2 text-xs text-ivory-400/70 bg-charcoal-800/70 rounded-full px-3 py-1 backdrop-blur z-20">
                  {formatTime(preview.created_at)} · {formatSize(preview.size)}
                </div>

                {/* 左右翻页按钮 */}
                {images.length > 1 && (
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

                {/* 图片容器 */}
                <motion.div
                  initial={{ scale: 0.9 }}
                  animate={{ scale: 1 }}
                  exit={{ scale: 0.9 }}
                  className="relative overflow-hidden flex items-center justify-center w-full h-full"
                  onClick={(e) => e.stopPropagation()}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  style={{ cursor: scale > 1 ? (isDragging ? "grabbing" : "grab") : "default" }}
                >
                  <img
                    src={preview.url}
                    alt={preview.filename}
                    draggable={false}
                    className="max-w-[90vw] max-h-[75vh] object-contain select-none rounded-lg shadow-2xl"
                    style={{
                      transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
                      transition: isDragging ? "none" : "transform 0.2s ease-out",
                    }}
                  />
                </motion.div>

                {/* 底部提示 */}
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[11px] text-ivory-500/60 bg-charcoal-800/70 rounded-full px-3 py-1 backdrop-blur">
                  滚轮缩放 · 拖拽移动 · ← → 翻页 · ESC 关闭
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </AnimatePresence>
  );
}
