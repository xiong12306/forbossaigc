import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  ImageIcon,
  Download,
  Trash2,
  Layers,
  Loader2,
} from "lucide-react";
import { assetsApi } from "@/platformApi";

// 筛选标签
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

// 卡片渐变占位（按 id 取模分配，保持视觉差异）
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

// 格式化时间，仅保留到分钟
function formatTime(s: string | null | undefined): string {
  if (!s) return "";
  // 兼容带时区与不带时区的时间戳
  const d = new Date(s.replace(" ", "T"));
  if (isNaN(d.getTime())) return s;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
}

export default function Assets() {
  const [filter, setFilter] = useState<string>("all");
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

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

  // 初次加载及筛选变化时拉取
  useEffect(() => {
    fetchAssets(filter === "all" ? undefined : filter);
  }, [filter]);

  const handleDelete = async (id: number) => {
    if (deletingId !== null) return;
    setDeletingId(id);
    try {
      await assetsApi.delete(id);
      await fetchAssets(filter === "all" ? undefined : filter);
    } catch (e) {
      console.error("删除素材失败:", e);
    } finally {
      setDeletingId(null);
    }
  };

  // 按当前筛选类型在客户端统计计数（顶栏与筛选标签）
  const totalCount = assets.length;

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      {/* 顶栏 */}
      <header className="flex items-center justify-between px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Layers className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="leading-none">
            <div className="font-serif text-xl text-gold-400 tracking-wide">素材库</div>
            <div className="text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">品牌素材资产管理</div>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-brown-800/60 border border-gold-500/20">
          <ImageIcon className="w-3.5 h-3.5 text-gold-400" />
          <span className="text-xs text-ivory-400/80">
            共 <span className="text-gold-300 font-medium">{totalCount}</span> 项
          </span>
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-6xl mx-auto">
          {/* 筛选标签 */}
          <div className="flex flex-wrap items-center gap-2 mb-8">
            {FILTERS.map((f) => {
              const active = filter === f.value;
              // 客户端计数：全部为总数；否则按 asset_type 过滤
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

          {/* 加载状态 */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-gold-400 animate-spin mb-3" />
              <div className="text-sm text-ivory-400/60">加载素材列表中...</div>
            </div>
          ) : assets.length > 0 ? (
            /* 图片网格 */
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {assets.map((asset, i) => {
                const isDeleting = deletingId === asset.id;
                return (
                  <motion.div
                    key={asset.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05, duration: 0.3 }}
                    className="group relative aspect-[4/3] rounded-xl overflow-hidden border border-gold-500/20 hover:border-gold-500/50 transition-all"
                  >
                    {/* 渐变占位块 */}
                    <div className={`absolute inset-0 bg-gradient-to-br ${gradientFor(asset.id)}`} />
                    <div
                      className="absolute inset-0 opacity-40"
                      style={{
                        background:
                          "radial-gradient(circle at 30% 30%, rgba(201,169,97,0.3), transparent 60%)",
                      }}
                    />
                    {/* 噪点纹理叠加 */}
                    <div
                      className="absolute inset-0 opacity-20 mix-blend-overlay"
                      style={{
                        backgroundImage:
                          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
                      }}
                    />

                    {/* 中央图标 */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <ImageIcon className="w-10 h-10 text-ivory-400/30 group-hover:scale-110 transition-transform" />
                    </div>

                    {/* 类型标签 */}
                    <div className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-black/40 backdrop-blur text-[11px] text-gold-300 border border-gold-500/30">
                      {TYPE_LABELS[asset.asset_type] || asset.asset_type}
                    </div>

                    {/* 底部信息 */}
                    <div className="absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-charcoal-900/90 via-charcoal-900/60 to-transparent">
                      <div className="text-sm text-ivory-500 font-medium truncate">
                        {asset.product_name || "未关联商品"}
                      </div>
                      <div className="text-[11px] text-ivory-400/60 mt-0.5">
                        {formatTime(asset.created_at)}
                      </div>
                    </div>

                    {/* hover 操作按钮 */}
                    <div className="absolute top-3 right-3 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        className="w-8 h-8 rounded-lg bg-black/50 backdrop-blur flex items-center justify-center text-gold-300 hover:bg-gold-500 hover:text-charcoal-900 transition"
                        title="下载"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(asset.id)}
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
      </div>
    </div>
  );
}
