import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  ShoppingCart,
  Percent,
  Users,
  Sparkles,
  Clock,
  Package,
  Image as ImageIcon,
  Type,
  Wand2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { dashboardApi } from "@/platformApi";

// 日期范围选项（UI 装饰，暂不联动后端）
const RANGES = [
  { value: "today", label: "今日" },
  { value: "7d", label: "7天" },
  { value: "30d", label: "30天" },
] as const;

type RangeValue = (typeof RANGES)[number]["value"];

type Overview = {
  gmv: number;
  gmv_change: number;
  orders: number;
  orders_change: number;
  visitors: number;
  visitors_change: number;
  conversion_rate: number;
  cr_change: number;
};

type SalesTrendItem = { date: string; gmv: number };
type TopProduct = { name: string; sales: number; gmv: number };
type RecentTask = {
  id: number | string;
  task_type: string;
  product: string;
  status: string;
  created_at: string;
};

// 根据 task_type 获取对应图标
function getTaskIcon(taskType: string) {
  const t = (taskType || "").toLowerCase();
  if (
    t.includes("image") ||
    t.includes("主图") ||
    t.includes("场景图") ||
    t.includes("图")
  ) {
    return ImageIcon;
  }
  if (
    t.includes("text") ||
    t.includes("标题") ||
    t.includes("文案") ||
    t.includes("文字")
  ) {
    return Type;
  }
  if (
    t.includes("poster") ||
    t.includes("海报") ||
    t.includes("marketing") ||
    t.includes("营销")
  ) {
    return Wand2;
  }
  return Sparkles;
}

// 格式化相对时间
function formatRelativeTime(iso: string) {
  if (!iso) return "—";
  const created = new Date(iso).getTime();
  if (isNaN(created)) return "—";
  const diff = Math.max(0, Date.now() - created);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  return `${days}天前`;
}

// 格式化日期为周X
function formatDateLabel(dateStr: string) {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const weekDays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return weekDays[d.getDay()];
}

// 格式化金额
function formatMoney(n: number) {
  return `¥${(n || 0).toLocaleString()}`;
}

// 格式化百分比
function formatPercent(n: number, digits = 1) {
  return `${(n || 0).toFixed(digits)}%`;
}

// 状态徽章颜色
function getStatusBadge(status: string) {
  const s = (status || "").toLowerCase();
  if (s.includes("done") || s.includes("完成") || s.includes("success")) {
    return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400";
  }
  if (s.includes("fail") || s.includes("失败") || s.includes("error")) {
    return "bg-terracotta-500/10 border-terracotta-500/30 text-terracotta-400";
  }
  return "bg-gold-500/10 border-gold-500/30 text-gold-300";
}

export default function Dashboard() {
  const [range, setRange] = useState<RangeValue>("7d");

  const [overview, setOverview] = useState<Overview | null>(null);
  const [salesTrend, setSalesTrend] = useState<SalesTrendItem[]>([]);
  const [topProducts, setTopProducts] = useState<TopProduct[]>([]);
  const [recentTasks, setRecentTasks] = useState<RecentTask[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [ov, trend, products, tasks] = await Promise.all([
          dashboardApi.overview(),
          dashboardApi.salesTrend(),
          dashboardApi.topProducts(),
          dashboardApi.recentTasks(),
        ]);
        if (cancelled) return;
        setOverview(ov as Overview);
        setSalesTrend((trend as SalesTrendItem[]) || []);
        setTopProducts((products as TopProduct[]) || []);
        setRecentTasks((tasks as RecentTask[]) || []);
      } catch (e: any) {
        if (cancelled) return;
        setError(e?.message || "数据加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const maxSales = Math.max(1, ...salesTrend.map((s) => s.gmv));

  // 数据卡片配置（基于 overview 数据动态生成）
  const stats = [
    {
      key: "gmv",
      label: "今日GMV",
      value: formatMoney(overview?.gmv ?? 0),
      change: overview?.gmv_change ?? 0,
      icon: DollarSign,
    },
    {
      key: "orders",
      label: "订单数",
      value: `${overview?.orders ?? 0}`,
      change: overview?.orders_change ?? 0,
      icon: ShoppingCart,
    },
    {
      key: "conv",
      label: "转化率",
      value: formatPercent(overview?.conversion_rate ?? 0),
      change: overview?.cr_change ?? 0,
      icon: Percent,
    },
    {
      key: "visitors",
      label: "访客数",
      value: `${(overview?.visitors ?? 0).toLocaleString()}`,
      change: overview?.visitors_change ?? 0,
      icon: Users,
    },
  ];

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      {/* 顶栏 */}
      <header className="flex items-center justify-between px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Sparkles className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="leading-none">
            <div className="font-serif text-xl text-gold-400 tracking-wide">数据看板</div>
            <div className="text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">经营数据总览</div>
          </div>
        </div>

        {/* 日期范围按钮组（UI 装饰，暂不联动后端） */}
        <div className="flex items-center gap-1 p-1 rounded-full bg-charcoal-900/60 border border-brown-700/60">
          {RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setRange(r.value)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${
                range === r.value
                  ? "bg-gold-500 text-charcoal-900 shadow-gold-glow"
                  : "text-ivory-400/70 hover:text-gold-300"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
              <Loader2 className="w-8 h-8 text-gold-400 animate-spin" />
              <div className="text-sm text-ivory-400/70">数据加载中…</div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3">
              <AlertCircle className="w-8 h-8 text-terracotta-400" />
              <div className="text-sm text-terracotta-400">{error}</div>
              <button
                onClick={() => window.location.reload()}
                className="mt-2 px-4 py-1.5 rounded-full text-xs bg-gold-500/15 border border-gold-500/30 text-gold-300 hover:bg-gold-500/25 transition"
              >
                重新加载
              </button>
            </div>
          ) : (
            <>
              {/* 数据卡片 2x2 网格 */}
              <div className="grid grid-cols-2 gap-4">
                {stats.map((stat, i) => {
                  const Icon = stat.icon;
                  const up = stat.change >= 0;
                  return (
                    <motion.div
                      key={stat.key}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 * i, duration: 0.4 }}
                      className="relative p-5 rounded-2xl bg-gradient-to-br from-brown-800/80 to-charcoal-800/60 border border-gold-500/20 shadow-warm-glow overflow-hidden"
                    >
                      {/* 右上角光晕 */}
                      <div
                        className="absolute -top-8 -right-8 w-28 h-28 rounded-full opacity-30 pointer-events-none"
                        style={{
                          background: "radial-gradient(circle, rgba(201,169,97,0.4), transparent 70%)",
                        }}
                      />
                      <div className="relative flex items-start justify-between">
                        <div>
                          <div className="text-xs text-ivory-400/60 tracking-wider">{stat.label}</div>
                          <div className="font-serif text-3xl text-ivory-500 mt-2">{stat.value}</div>
                        </div>
                        <div className="w-10 h-10 rounded-xl bg-gold-500/15 border border-gold-500/30 flex items-center justify-center">
                          <Icon className="w-5 h-5 text-gold-300" />
                        </div>
                      </div>
                      <div
                        className={`relative mt-3 inline-flex items-center gap-1 text-xs font-medium ${
                          up ? "text-emerald-400" : "text-terracotta-400"
                        }`}
                      >
                        {up ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                        <span>
                          {up ? "↑" : "↓"} {Math.abs(stat.change)}%
                        </span>
                        <span className="text-ivory-400/40 ml-1">较昨日</span>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* 销售趋势条形图 */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.4 }}
                className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
              >
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-gold-400" />
                    <h3 className="font-serif text-lg text-gold-300">销售趋势</h3>
                  </div>
                  <span className="text-xs text-ivory-400/50">近 {salesTrend.length} 天 GMV</span>
                </div>
                {salesTrend.length === 0 ? (
                  <div className="h-48 flex items-center justify-center text-sm text-ivory-400/50">
                    暂无销售数据
                  </div>
                ) : (
                  <div className="flex items-end justify-between gap-3 h-48">
                    {salesTrend.map((s, i) => {
                      const heightPct = Math.round((s.gmv / maxSales) * 100);
                      return (
                        <div
                          key={`${s.date}-${i}`}
                          className="flex-1 flex flex-col items-center gap-2 group"
                        >
                          <div className="relative w-full flex-1 flex items-end">
                            <div
                              className="w-full rounded-t-lg transition-all duration-500 group-hover:opacity-90"
                              style={{
                                height: `${heightPct}%`,
                                background:
                                  "linear-gradient(to top, #B89650 0%, #D4B970 50%, #E0C988 100%)",
                                boxShadow: "0 0 12px rgba(201, 169, 97, 0.3)",
                                animationDelay: `${i * 60}ms`,
                              }}
                            />
                            {/* 顶部数值 */}
                            <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-gold-300/80 whitespace-nowrap">
                              ¥{(s.gmv / 1000).toFixed(1)}k
                            </div>
                          </div>
                          <div className="text-[11px] text-ivory-400/60">{formatDateLabel(s.date)}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>

              {/* 双栏：热销商品 + AI 任务 */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 热销商品 Top5 */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.3, duration: 0.4 }}
                  className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
                >
                  <div className="flex items-center gap-2 mb-5">
                    <Package className="w-4 h-4 text-gold-400" />
                    <h3 className="font-serif text-lg text-gold-300">热销商品 Top5</h3>
                  </div>
                  {topProducts.length === 0 ? (
                    <div className="py-10 text-center text-sm text-ivory-400/50">暂无商品数据</div>
                  ) : (
                    <ul className="space-y-3">
                      {topProducts.slice(0, 5).map((p, i) => {
                        const rank = i + 1;
                        return (
                          <li
                            key={`${p.name}-${i}`}
                            className="flex items-center gap-3 p-3 rounded-xl bg-charcoal-900/40 border border-brown-700/40 hover:border-gold-500/30 transition"
                          >
                            <span
                              className={`flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-serif font-semibold ${
                                rank === 1
                                  ? "bg-gold-500 text-charcoal-900 shadow-gold-glow"
                                  : "bg-brown-700/60 text-gold-300"
                              }`}
                            >
                              {rank}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-ivory-500 truncate">{p.name}</div>
                              <div className="text-[11px] text-ivory-400/50 mt-0.5">
                                销量 {p.sales} 件
                              </div>
                            </div>
                            <div className="text-sm font-serif text-gold-300">
                              ¥{(p.gmv || 0).toLocaleString()}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </motion.div>

                {/* 最近 AI 任务 */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.35, duration: 0.4 }}
                  className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
                >
                  <div className="flex items-center gap-2 mb-5">
                    <Sparkles className="w-4 h-4 text-gold-400" />
                    <h3 className="font-serif text-lg text-gold-300">最近 AI 任务</h3>
                  </div>
                  {recentTasks.length === 0 ? (
                    <div className="py-10 text-center text-sm text-ivory-400/50">暂无任务数据</div>
                  ) : (
                    <ul className="space-y-3">
                      {recentTasks.slice(0, 6).map((task) => {
                        const Icon = getTaskIcon(task.task_type);
                        return (
                          <li
                            key={task.id}
                            className="flex items-center gap-3 p-3 rounded-xl bg-charcoal-900/40 border border-brown-700/40 hover:border-gold-500/30 transition"
                          >
                            <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-gold-500/10 border border-gold-500/25 flex items-center justify-center">
                              <Icon className="w-4 h-4 text-gold-300" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm text-ivory-500 truncate">{task.task_type}</div>
                              <div className="text-[11px] text-ivory-400/50 mt-0.5 truncate">
                                {task.product || "—"}
                              </div>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span
                                className={`px-2 py-0.5 rounded-full border text-[10px] ${getStatusBadge(
                                  task.status
                                )}`}
                              >
                                {task.status}
                              </span>
                              <span className="flex items-center gap-1 text-[10px] text-ivory-400/40">
                                <Clock className="w-2.5 h-2.5" />
                                {formatRelativeTime(task.created_at)}
                              </span>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </motion.div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
