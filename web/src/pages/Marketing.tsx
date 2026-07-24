import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Megaphone,
  Ticket,
  Flame,
  Users,
  ChevronRight,
  Calendar,
  Clock,
  Percent,
  Loader2,
} from "lucide-react";
import { marketingApi } from "@/platformApi";

// 活动类型标签样式
const TYPE_META: Record<string, { label: string; cls: string }> = {
  flash_sale: {
    label: "限时秒杀",
    cls: "text-terracotta-400 bg-terracotta-500/10 border-terracotta-500/30",
  },
  full_reduction: {
    label: "满减活动",
    cls: "text-gold-300 bg-gold-500/10 border-gold-500/30",
  },
  new_user: {
    label: "新人专享",
    cls: "text-ivory-400 bg-brown-800/60 border-brown-700/60",
  },
  group_buy: {
    label: "拼团",
    cls: "text-gold-400 bg-brown-700/60 border-gold-500/30",
  },
};

// 活动状态样式
const STATUS_META: Record<string, { label: string; cls: string; dot: string }> = {
  active: {
    label: "进行中",
    cls: "text-gold-300 bg-gold-500/10 border-gold-500/30",
    dot: "bg-gold-400",
  },
  upcoming: {
    label: "即将开始",
    cls: "text-ivory-400 bg-brown-800/60 border-brown-700/60",
    dot: "bg-ivory-400/60",
  },
  ended: {
    label: "已结束",
    cls: "text-terracotta-400/50 bg-terracotta-500/10 border-terracotta-500/30",
    dot: "bg-terracotta-500/40",
  },
};

// 优惠券类型标签
const COUPON_LABEL: Record<string, string> = {
  full_reduction: "满减券",
  discount: "折扣券",
  new_user: "新人券",
};

interface Campaign {
  id: number | string;
  name: string;
  type: string;
  start_date: string;
  end_date: string;
  status: "active" | "upcoming" | "ended";
  discount_value?: string | number;
  conditions?: string;
  created_at?: string;
}

interface Coupon {
  id: number | string;
  name: string;
  type: string;
  value: string | number;
  condition_amount?: number;
  claimed_count: number;
  total_count: number;
  status?: string;
  created_at?: string;
}

// 三类工具卡片基础配置
const TOOL_BASE = [
  {
    key: "coupon",
    title: "优惠券管理",
    icon: Ticket,
    gradient: "from-gold-500 to-gold-300",
  },
  {
    key: "promo",
    title: "促销活动",
    icon: Flame,
    gradient: "from-terracotta-500 to-gold-400",
  },
  {
    key: "community",
    title: "社群运营",
    icon: Users,
    gradient: "from-brown-700 to-gold-500",
  },
] as const;

// 优惠券展示金额格式化
function formatCouponAmount(c: Coupon): string {
  const v = c.value;
  if (c.type === "discount") {
    return typeof v === "number" ? `${v}折` : String(v);
  }
  if (c.type === "new_user") {
    return `立减${v}`;
  }
  // full_reduction
  const cond = c.condition_amount ? `满${c.condition_amount}` : "";
  return `${cond}减${v}`;
}

export default function Marketing() {
  const [activeTool, setActiveTool] = useState<string>("coupon");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [camps, cps] = await Promise.all([
          marketingApi.campaigns(),
          marketingApi.coupons(),
        ]);
        if (cancelled) return;
        setCampaigns(camps ?? []);
        setCoupons(cps ?? []);
      } catch (err) {
        console.error("加载营销数据失败:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // 统计数据动态计算
  const activeCouponCount = coupons.filter((c) => c.status === "active").length;
  const upcomingCampaignCount = campaigns.filter(
    (c) => c.status === "upcoming"
  ).length;

  const TOOLS = [
    { ...TOOL_BASE[0], subtitle: `${activeCouponCount}个进行中` },
    { ...TOOL_BASE[1], subtitle: `${upcomingCampaignCount}个即将开始` },
    { ...TOOL_BASE[2], subtitle: "5个活跃群" },
  ];

  return (
    <div className="min-h-screen bg-charcoal-900 text-ivory-500">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* 顶部标题 */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Megaphone className="w-5 h-5 text-charcoal-900" />
          </div>
          <div>
            <h1 className="font-serif text-3xl text-gold-300 tracking-wide">营销工具</h1>
            <p className="text-xs text-ivory-400/60 mt-1 tracking-[0.15em]">
              优惠券 · 促销活动 · 社群运营
            </p>
          </div>
        </motion.header>

        {/* 工具卡片 */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          {TOOLS.map((tool, idx) => {
            const Icon = tool.icon;
            const isActive = activeTool === tool.key;
            return (
              <motion.button
                key={tool.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: idx * 0.06 }}
                whileHover={{ scale: 1.03, y: -2 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTool(tool.key)}
                className={`relative text-left p-5 rounded-2xl border transition-all overflow-hidden ${
                  isActive
                    ? "border-gold-500 bg-gold-500/10 shadow-gold-glow"
                    : "border-brown-700/60 bg-charcoal-800/60 hover:border-gold-500/40"
                }`}
              >
                {/* 装饰光晕 */}
                <div
                  className={`absolute -top-8 -right-8 w-28 h-28 rounded-full bg-gradient-to-br ${tool.gradient} opacity-20 blur-2xl pointer-events-none`}
                />
                <div className="flex items-start justify-between relative">
                  <div
                    className={`w-12 h-12 rounded-xl bg-gradient-to-br ${tool.gradient} flex items-center justify-center`}
                  >
                    <Icon className="w-6 h-6 text-charcoal-900" />
                  </div>
                  <ChevronRight
                    className={`w-4 h-4 mt-1 transition ${
                      isActive ? "text-gold-300" : "text-ivory-400/30"
                    }`}
                  />
                </div>
                <div className="mt-4 relative">
                  <div className="font-serif text-lg text-ivory-500">{tool.title}</div>
                  <div className="text-xs text-gold-300/80 mt-1">{tool.subtitle}</div>
                </div>
              </motion.button>
            );
          })}
        </div>

        {/* 加载状态 */}
        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="w-8 h-8 text-gold-400 animate-spin" />
          </div>
        ) : (
          <>
            {/* 进行中的活动 */}
            <section className="mb-8">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-serif text-xl text-gold-300 flex items-center gap-2">
                  <Flame className="w-4 h-4" />
                  进行中的活动
                </h2>
                <button className="text-xs text-ivory-400/60 hover:text-gold-300 transition">
                  查看全部 →
                </button>
              </div>

              {campaigns.length === 0 ? (
                <div className="px-5 py-10 rounded-xl bg-charcoal-800/60 border border-brown-700/40 text-center text-sm text-ivory-400/50">
                  暂无活动数据
                </div>
              ) : (
                <div className="space-y-2">
                  {campaigns.map((a, idx) => {
                    const typeMeta = TYPE_META[a.type] ?? {
                      label: a.type,
                      cls: "text-ivory-400 bg-brown-800/60 border-brown-700/60",
                    };
                    const statusMeta = STATUS_META[a.status] ?? STATUS_META.active;
                    return (
                      <motion.div
                        key={a.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3, delay: idx * 0.05 }}
                        className="flex items-center justify-between px-5 py-4 rounded-xl bg-charcoal-800/60 border border-brown-700/40 hover:border-gold-500/40 transition"
                      >
                        <div className="flex items-center gap-4 min-w-0">
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-brown-700 to-charcoal-900 flex items-center justify-center flex-shrink-0">
                            <Calendar className="w-4 h-4 text-gold-400" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm text-ivory-500 font-medium truncate">
                              {a.name}
                            </div>
                            <div className="flex items-center gap-2 mt-1 text-xs text-ivory-400/50">
                              <Clock className="w-3 h-3" />
                              <span>
                                {a.start_date} ~ {a.end_date}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span
                            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs border ${typeMeta.cls}`}
                          >
                            {typeMeta.label}
                          </span>
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border ${statusMeta.cls}`}
                          >
                            <span className={`w-1.5 h-1.5 rounded-full ${statusMeta.dot}`} />
                            {statusMeta.label}
                          </span>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* 优惠券列表 */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-serif text-xl text-gold-300 flex items-center gap-2">
                  <Ticket className="w-4 h-4" />
                  优惠券列表
                </h2>
                <button className="text-xs px-3 py-1.5 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 transition">
                  + 新建优惠券
                </button>
              </div>

              {coupons.length === 0 ? (
                <div className="px-5 py-10 rounded-xl bg-charcoal-800/60 border border-brown-700/40 text-center text-sm text-ivory-400/50">
                  暂无优惠券数据
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {coupons.map((c, idx) => {
                    const percent =
                      c.total_count > 0
                        ? Math.round((c.claimed_count / c.total_count) * 100)
                        : 0;
                    return (
                      <motion.div
                        key={c.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: idx * 0.06 }}
                        whileHover={{ y: -3 }}
                        className="relative p-5 rounded-2xl bg-gradient-to-br from-brown-800/80 to-charcoal-900 border border-gold-500/20 hover:border-gold-500/50 transition overflow-hidden"
                      >
                        {/* 左侧装饰条 */}
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-gold-400 to-terracotta-500" />
                        {/* 右上角图标 */}
                        <Percent className="absolute top-4 right-4 w-5 h-5 text-gold-500/30" />

                        <div className="text-xs text-ivory-400/60 tracking-wider uppercase">
                          {COUPON_LABEL[c.type] ?? "优惠券"}
                        </div>
                        <div className="font-serif text-2xl text-gold-300 mt-2">
                          {formatCouponAmount(c)}
                        </div>
                        <div className="text-xs text-ivory-400/50 mt-2">{c.name}</div>

                        {/* 进度条 */}
                        <div className="mt-4">
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-ivory-400/60">已领取</span>
                            <span className="text-gold-300">
                              {c.claimed_count} / {c.total_count}
                            </span>
                          </div>
                          <div className="h-1.5 rounded-full bg-brown-900/80 overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${percent}%` }}
                              transition={{ duration: 0.6, delay: 0.3 + idx * 0.1 }}
                              className="h-full bg-gradient-to-r from-gold-500 to-terracotta-500"
                            />
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
