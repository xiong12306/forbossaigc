import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { X, ZoomIn, ZoomOut, RotateCcw, Download, ChevronLeft, ChevronRight } from "lucide-react";

export interface LightboxImage {
  url: string;
  label?: string;
}

interface Props {
  images: LightboxImage[];
  index: number | null;
  onClose: () => void;
  onIndexChange: (i: number) => void;
}

/**
 * 全屏图片查看器：滚轮缩放、拖动平移、键盘导航、下载
 */
export default function ImageLightbox({ images, index, onClose, onIndexChange }: Props) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const current = index !== null ? images[index] : null;

  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const goPrev = () => {
    if (index === null) return;
    onIndexChange((index - 1 + images.length) % images.length);
    resetZoom();
  };

  const goNext = () => {
    if (index === null) return;
    onIndexChange((index + 1) % images.length);
    resetZoom();
  };

  const zoomIn = () => setScale((s) => Math.min(s * 1.3, 5));
  const zoomOut = () => setScale((s) => Math.max(s / 1.3, 0.5));

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (e.deltaY < 0) zoomIn();
    else zoomOut();
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (scale <= 1) return;
    e.preventDefault();
    setIsDragging(true);
    dragStart.current = { x: e.clientX - position.x, y: e.clientY - position.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({ x: e.clientX - dragStart.current.x, y: e.clientY - dragStart.current.y });
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!current) return;
    try {
      const res = await fetch(current.url);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `image_${(index ?? 0) + 1}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      window.open(current.url, "_blank");
    }
  };

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (index === null) return;
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") goPrev();
      if (e.key === "ArrowRight") goNext();
      if (e.key === "+" || e.key === "=") zoomIn();
      if (e.key === "-") zoomOut();
      if (e.key === "0") resetZoom();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [index, images.length]);

  if (!current) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
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
        <span className="text-xs text-ivory-400 w-14 text-center select-none">
          {Math.round(scale * 100)}%
        </span>
        <button
          onClick={zoomIn}
          className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
          title="放大 (+)"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={resetZoom}
          className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
          title="重置 (0)"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-5 bg-gold-500/20 mx-0.5" />
        <button
          onClick={handleDownload}
          className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
          title="下载"
        >
          <Download className="w-4 h-4" />
        </button>
        <div className="w-px h-5 bg-gold-500/20 mx-0.5" />
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-full hover:bg-red-500/20 flex items-center justify-center text-ivory-300 hover:text-red-400 transition"
          title="关闭 (Esc)"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* 图片 */}
      <motion.img
        key={current.url}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.2 }}
        src={current.url}
        alt={current.label || "生成图片"}
        draggable={false}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={(e) => e.stopPropagation()}
        className="max-w-[90vw] max-h-[85vh] object-contain select-none"
        style={{
          transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
          cursor: scale > 1 ? (isDragging ? "grabbing" : "grab") : "default",
          transition: isDragging ? "none" : "transform 0.15s ease-out",
        }}
      />

      {/* 标签 */}
      {current.label && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-charcoal-800/80 border border-gold-500/20 text-gold-300 text-xs backdrop-blur">
          {current.label}
        </div>
      )}

      {/* 左右切换 */}
      {images.length > 1 && (
        <>
          <button
            onClick={(e) => { e.stopPropagation(); goPrev(); }}
            className="absolute left-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-charcoal-800/80 border border-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 hover:bg-gold-500/10 transition"
            title="上一张 (←)"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); goNext(); }}
            className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-charcoal-800/80 border border-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 hover:bg-gold-500/10 transition"
            title="下一张 (→)"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          {/* 计数器 */}
          <div className="absolute bottom-4 right-4 px-2.5 py-1 rounded-full bg-charcoal-800/80 border border-gold-500/20 text-ivory-400 text-xs backdrop-blur">
            {(index ?? 0) + 1} / {images.length}
          </div>
        </>
      )}
    </motion.div>
  );
}
