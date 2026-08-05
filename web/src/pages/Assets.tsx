import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ImageIcon,
  Download,
  Trash2,
  Layers,
  Loader2,
  X,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { assetsApi } from "@/platformApi";

const FILTERS = [
  { value: "all", label: "全部" },
  { value: "main", label: "主图" },
  { value: "detail", label: "详情图" },
  { value: "scene", label: "场景图" },
  { value: "poster", label: "海报" },
  { value: "carousel", label: "轮播图" },
] as const;

interface AssetItem {
  id: number;
  asset_type: string;
  product_name: string;
  url: string | null;
  thumbnail_url: string | null;
  task_id: number | null;
  created_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  main: "主图",
  detail: "详情图",
  scene: "场景图",
  poster: "海报",
  carousel: "轮播图",
};

const GRADIENTS = [
  "from-gold-500/40 via-terracotta-500/30 to-brown-700",
  "from-brown-700 via-gold-500/30 to-charcoal-800",
  "from-terracotta-500/40 via-brown-700 to-gold-500/20",
  "from-gold-500/30 via-terracotta-500/40 to-brown-800",
  "from-brown-800 via-gold-500/40 to-terracotta-500/30",
  "from-charcoal-800 via-brown-700 to-gold-500/30",
  "from-gold-500/40 via-brown-800 to-terracotta-500/20",
  "from-terracotta-500/30 via-gold-500/30 to-brown-700",
];

function gradientFor(id: number) {
  return GRADIENTS[id % GRADIENTS.length];
}

function formatTime(s: string | null | undefined): string {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T"));
  if (isNaN(d.getTime())) return s;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

function isRealUrl(url: string | null | undefined): boolean {
  return !!url && !url.startsWith("mock://");
}

function getDisplayUrl(asset: AssetItem): string | null {
  const url = asset.url || asset.thumbnail_url;
  return isRealUrl(url) ? url : null;
}

export default function Assets() {
  const [filter, setFilter] = useState<string>("all");
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });

  const realAssets = assets.filter((a) => getDisplayUrl(a));
  const preview = previewIndex !== null ? assets[previewIndex] : null;

  const resetZoom = () => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  };

  const openPreview = (asset: AssetItem) => {
    const idx = assets.findIndex((a) => a.id === asset.id);
    setPreviewIndex(idx);
    resetZoom();
  };

  const closePreview = () => {
    setPreviewIndex(null);
    resetZoom();
  };

  const goPrev = () => {
    if (previewIndex === null || realAssets.length <= 1) return;
    const currentAsset = assets[previewIndex];
    const realIdxs = assets
      .map((a, i) => (getDisplayUrl(a) ? i : -1))
      .filter((i) => i >= 0);
    const realIdxPos = realIdxs.indexOf(previewIndex);
    const prevRealIdx = (realIdxPos - 1 + realIdxs.length) % realIdxs.length;
    setPreviewIndex(realIdxs[prevRealIdx]);
    resetZoom();
  };

  const goNext = () => {
    if (previewIndex === null || realAssets.length <= 1) return;
    const realIdxs = assets
      .map((a, i) => (getDisplayUrl(a) ? i : -1))
      .filter((i) => i >= 0);
    const realIdxPos = realIdxs.indexOf(previewIndex);
    const nextRealIdx = (realIdxPos + 1) % realIdxs.length;
    setPreviewIndex(realIdxs[nextRealIdx]);
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
  }, [previewIndex, assets.length]);

  const fetchAssets = async (type?: string) => {
    setLoading(true);
    try {
      const data = await assetsApi.list(type);
      setAssets(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("获取素材列表失败:", e);
      setAssets([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets(filter === "all" ? undefined : filter);
  }, [filter]);

  const handleDelete = async (id: number) => {
    if (deletingId !== null) return;
    setDeletingId(id);
    try {
      await assetsApi.delete(id);
      if (previewIndex !== null) {
        const currentAsset = assets[previewIndex];
        if (currentAsset?.id === id) {
          closePreview();
        }
      }
      await fetchAssets(filter === "all" ? undefined : filter);
    } catch (e) {
      console.error("删除素材失败:", e);
    } finally {
      setDeletingId(null);
    }
  };

  const totalCount = assets.length;

  return (
    <div className="min-h-full p-4 lg:p-6 text-ivory-500">
      {/* 顶部工具栏：计数 */}
      <div className="flex justify-end mb-6">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-brown-800/60 border border-gold-500/20">
          <ImageIcon className="w-3.5 h-3.5 text-gold-400" />
          <span className="text-xs text-ivory-400/80">
            共 <span className="text-gold-300 font-medium">{totalCount}</span> 项
          </span>
        </div>
      </div>

      <div className="max-w-6xl mx-auto">
          <div className="flex flex-wrap items-center gap-2 mb-8">
            {FILTERS.map((f) => {
              const active = filter === f.value;
              const count =
                f.value === "all"
                  ? totalCount
                  : assets.filter((a) => a.asset_type === f.value).length;
              return (
                <motion.button
                  key={f.value}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={() => setFilter(f.value)}
                  className={`px-4 py-2 rounded-full text-xs border transition-all flex items-center gap-1.5 ${
                    active
                      ? "border-gold-500 bg-gold-500/15 text-gold-300 shadow-gold-glow"
                      : "border-brown-700/60 text-ivory-400/70 hover:border-gold-500/40"
                  }`}
                >
                  {f.label}
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      active ? "bg-gold-500/20 text-gold-300" : "bg-brown-800/60 text-ivory-400/50"
                    }`}
                  >
                    {count}
                  </span>
                </motion.button>
              );
            })}
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-gold-400 animate-spin mb-3" />
              <div className="text-sm text-ivory-400/60">加载素材列表中...</div>
            </div>
          ) : assets.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {assets.map((asset, i) => {
                const isDeleting = deletingId === asset.id;
                const imgUrl = getDisplayUrl(asset);
                return (
                  <motion.div
                    key={asset.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05, duration: 0.3 }}
                    className="group relative aspect-[4/3] rounded-xl overflow-hidden border border-gold-500/20 hover:border-gold-500/50 transition-all bg-brown-900/40"
                  >
                    {imgUrl ? (
                      /* 真实图片 */
                      <>
                        <img
                          src={imgUrl}
                          alt={asset.product_name || "素材"}
                          loading="lazy"
                          onClick={() => openPreview(asset)}
                          className="absolute inset-0 w-full h-full object-cover cursor-pointer group-hover:scale-105 transition-transform duration-500"
                        />
                        {/* 常驻右下角放大图标 */}
                        <div
                          className="absolute bottom-1.5 right-1.5 w-6 h-6 rounded-full bg-black/50 backdrop-blur flex items-center justify-center z-10 opacity-80 pointer-events-none"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <ZoomIn className="w-3.5 h-3.5 text-white" />
                        </div>
                      </>
                    ) : (
                      /* 无URL时降级为渐变占位 */
                      <>
                        <div className={`absolute inset-0 bg-gradient-to-br ${gradientFor(asset.id)}`} />
                        <div
                          className="absolute inset-0 opacity-40"
                          style={{
                            background:
                              "radial-gradient(circle at 30% 30%, rgba(37, 99, 235,0.3), transparent 60%)",
                          }}
                        />
                        <div
                          className="absolute inset-0 opacity-20 mix-blend-overlay"
                          style={{
                            backgroundImage:
                              "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
                          }}
                        />
                        <div className="absolute inset-0 flex items-center justify-center">
                          <ImageIcon className="w-10 h-10 text-ivory-400/30" />
                        </div>
                      </>
                    )}

                    {/* 类型标签 */}
                    <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/50 backdrop-blur text-[11px] text-gold-300 border border-gold-500/30 z-10">
                      {TYPE_LABELS[asset.asset_type] || asset.asset_type}
                    </div>

                    {/* 底部信息 */}
                    <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-charcoal-900/90 via-charcoal-900/60 to-transparent z-10">
                      <div className="text-sm text-ivory-500 font-medium truncate">
                        {asset.product_name || "未关联商品"}
                      </div>
                      <div className="text-[11px] text-ivory-400/60 mt-0.5">
                        {formatTime(asset.created_at)}
                      </div>
                    </div>

                    {/* hover 操作按钮 */}
                    <div className="absolute top-3 right-3 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                      {imgUrl && (
                        <a
                          href={imgUrl}
                          download
                          onClick={(e) => e.stopPropagation()}
                          className="w-8 h-8 rounded-lg bg-black/50 backdrop-blur flex items-center justify-center text-gold-300 hover:bg-gold-500 hover:text-charcoal-900 transition"
                          title="下载"
                        >
                          <Download className="w-4 h-4" />
                        </a>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(asset.id);
                        }}
                        disabled={isDeleting}
                        className="w-8 h-8 rounded-lg bg-black/50 backdrop-blur flex items-center justify-center text-terracotta-300 hover:bg-terracotta-500 hover:text-charcoal-900 transition disabled:opacity-60"
                        title="删除"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 rounded-full bg-brown-800/60 border border-gold-500/20 flex items-center justify-center mb-4">
                <ImageIcon className="w-8 h-8 text-ivory-400/40" />
              </div>
              <div className="font-serif text-lg text-ivory-400/60 mb-1">暂无素材</div>
              <div className="text-xs text-ivory-400/40">该分类下还没有任何素材</div>
            </div>
          )}
        </div>

      {/* 大图预览 - 增强版 */}
      <AnimatePresence>
        {preview && getDisplayUrl(preview) && (
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
                href={getDisplayUrl(preview)!}
                download
                onClick={(e) => e.stopPropagation()}
                className="w-8 h-8 rounded-full hover:bg-gold-500/20 flex items-center justify-center text-ivory-300 hover:text-gold-300 transition"
                title="下载原图"
              >
                <Download className="w-4 h-4" />
              </a>
            </div>

            {/* 图片计数器 */}
            {realAssets.length > 1 && (
              <div className="absolute top-4 right-4 bg-charcoal-800/90 border border-gold-500/20 rounded-full px-3 py-1.5 text-xs text-ivory-400 backdrop-blur z-20">
                {assets
                  .map((a, i) => (getDisplayUrl(a) ? i : -1))
                  .filter((i) => i >= 0)
                  .indexOf(previewIndex!) + 1}{" "}
                / {realAssets.length}
              </div>
            )}

            {/* 图片信息 */}
            <div className="absolute bottom-16 left-1/2 -translate-x-1/2 text-xs text-ivory-400/70 bg-charcoal-800/70 rounded-full px-3 py-1 backdrop-blur z-20">
              {preview.product_name || "素材"} · {TYPE_LABELS[preview.asset_type] || preview.asset_type} · {formatTime(preview.created_at)}
            </div>

            {/* 左右翻页按钮 */}
            {realAssets.length > 1 && (
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
                src={getDisplayUrl(preview)!}
                alt={preview.product_name || "素材预览"}
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
    </div>
  );
}
