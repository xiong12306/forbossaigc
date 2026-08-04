import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  ArrowDownLeft,
  ArrowUpRight,
  Receipt,
  Coins,
  Megaphone,
  Truck,
  Palette,
  Percent,
  Sparkles,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { financeApi } from "@/platformApi";

type Summary = {
  income: number;
  expense: number;
  profit: number;
  profit_rate: number;
};

type FinanceRecord = {
  id: number;
  record_type: string;
  category: string;
  amount: number;
  description: string;
  record_date: string;
};

type MonthlyItem = { month: string; income: number; expense: number };

// 根据 category 获取支出图标
function getExpenseIcon(category: string) {
  const c = (category || "").toLowerCase();
  if (c.includes("佣金") || c.includes("commission") || c.includes("平台")) return Coins;
  if (c.includes("广告") || c.includes("ad") || c.includes("营销") || c.includes("投放")) {
    return Megaphone;
  }
  if (c.includes("物流") || c.includes("快递") || c.includes("logistics") || c.includes("shipping")) {
    return Truck;
  }
  if (c.includes("素材") || c.includes("制作") || c.includes("material") || c.includes("拍摄")) {
    return Palette;
  }
  return Coins;
}

export default function Finance() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [monthly, setMonthly] = useState<MonthlyItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [s, rs, mc] = await Promise.all([
          financeApi.summary(),
          financeApi.records(),
          financeApi.monthlyComparison(),
        ]);
        if (cancelled) return;
        setSummary(s as Summary);
        setRecords((rs as FinanceRecord[]) || []);
        setMonthly((mc as MonthlyItem[]) || []);
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

  const monthlyMax = Math.max(1, ...monthly.flatMap((m) => [m.income, m.expense]));

  // 按类别聚合支出记录
  const expenses = useMemo(() => {
    const grouped: Record<string, { amount: number; description: string }> = {};
    for (const r of records) {
      if ((r.record_type || "").toLowerCase() !== "expense") continue;
      const key = r.category || "其他";
      if (!grouped[key]) grouped[key] = { amount: 0, description: "" };
      grouped[key].amount += r.amount || 0;
      if (r.description && !grouped[key].description) {
        grouped[key].description = r.description;
      }
    }
    return Object.entries(grouped)
      .map(([name, info]) => ({ name, amount: info.amount, description: info.description }))
      .sort((a, b) => b.amount - a.amount);
  }, [records]);

  const totalExpense = expenses.reduce((sum, e) => sum + e.amount, 0);

  const income = summary?.income ?? 0;
  const expenseVal = summary?.expense ?? 0;
  const profit = summary?.profit ?? 0;
  const profitMargin =
    summary?.profit_rate != null ? Number(summary.profit_rate).toFixed(1) : "0.0";

  const accentMap = {
    gold: {
      ring: "bg-gold-500/15 border-gold-500/30",
      icon: "text-gold-300",
    },
    terracotta: {
      ring: "bg-terracotta-500/15 border-terracotta-500/30",
      icon: "text-terracotta-400",
    },
    emerald: {
      ring: "bg-emerald-500/15 border-emerald-500/30",
      icon: "text-emerald-400",
    },
  } as const;

  const overviews = [
    {
      key: "income",
      label: "本月收入",
      value: `¥${income.toLocaleString()}`,
      icon: ArrowDownLeft,
      accent: "gold" as const,
    },
    {
      key: "expense",
      label: "本月支出",
      value: `¥${expenseVal.toLocaleString()}`,
      icon: ArrowUpRight,
      accent: "terracotta" as const,
    },
    {
      key: "profit",
      label: "净利润",
      value: `¥${profit.toLocaleString()}`,
      icon: Wallet,
      accent: "emerald" as const,
    },
  ];

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      {/* 顶栏 */}
      <header className="flex items-center justify-between px-4 lg:px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Receipt className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="leading-none">
            <div className="font-serif text-xl text-gold-400 tracking-wide">财务看板</div>
            <div className="text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">收支利润分析</div>
          </div>
        </div>
        <span className="px-3 py-1.5 rounded-full text-xs text-gold-300 border border-gold-500/30 bg-gold-500/10">
          {new Date().getFullYear()}年{new Date().getMonth() + 1}月
        </span>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto px-4 lg:px-6 py-4 lg:py-6">
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
              {/* 概览卡片 */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {overviews.map((item, i) => {
                  const Icon = item.icon;
                  const accent = accentMap[item.accent];
                  return (
                    <motion.div
                      key={item.key}
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.05 * i, duration: 0.4 }}
                      className="relative p-6 rounded-2xl bg-gradient-to-br from-brown-800/80 to-charcoal-800/60 border border-gold-500/20 shadow-warm-glow overflow-hidden"
                    >
                      <div
                        className="absolute -top-8 -right-8 w-28 h-28 rounded-full opacity-30 pointer-events-none"
                        style={{
                          background: "radial-gradient(circle, rgba(37, 99, 235,0.4), transparent 70%)",
                        }}
                      />
                      <div className="relative flex items-start justify-between">
                        <div>
                          <div className="text-xs text-ivory-400/60 tracking-wider">{item.label}</div>
                          <div className="font-serif text-3xl text-ivory-500 mt-2">{item.value}</div>
                        </div>
                        <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${accent.ring}`}>
                          <Icon className={`w-5 h-5 ${accent.icon}`} />
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>

              {/* 利润率展示条 */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2, duration: 0.4 }}
                className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Percent className="w-4 h-4 text-gold-400" />
                    <h3 className="font-serif text-lg text-gold-300">利润率</h3>
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="font-serif text-3xl text-emerald-400">{profitMargin}</span>
                    <span className="text-sm text-ivory-400/60">%</span>
                  </div>
                </div>
                {/* 利润率进度条 */}
                <div className="relative h-3 rounded-full bg-charcoal-900/60 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(100, Number(profitMargin) || 0)}%` }}
                    transition={{ delay: 0.4, duration: 0.8, ease: "easeOut" }}
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      background: "linear-gradient(to right, #1D4ED8 0%, #3B82F6 50%, #3B82F6 100%)",
                      boxShadow: "0 0 12px rgba(37, 99, 235, 0.4)",
                    }}
                  />
                </div>
                <div className="flex items-center justify-between mt-2 text-[11px] text-ivory-400/50">
                  <span>收入 ¥{income.toLocaleString()}</span>
                  <span>支出 ¥{expenseVal.toLocaleString()}</span>
                  <span>利润 ¥{profit.toLocaleString()}</span>
                </div>
              </motion.div>

              {/* 收支对比条形图 */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.25, duration: 0.4 }}
                className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
              >
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-gold-400" />
                    <h3 className="font-serif text-lg text-gold-300">收支对比</h3>
                  </div>
                  {/* 图例 */}
                  <div className="flex items-center gap-4 text-[11px]">
                    <span className="flex items-center gap-1.5 text-ivory-400/70">
                      <span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#3B82F6" }} />
                      收入
                    </span>
                    <span className="flex items-center gap-1.5 text-ivory-400/70">
                      <span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#0EA5E9" }} />
                      支出
                    </span>
                  </div>
                </div>
                {monthly.length === 0 ? (
                  <div className="h-52 flex items-center justify-center text-sm text-ivory-400/50">
                    暂无月度对比数据
                  </div>
                ) : (
                  <div className="flex items-end justify-between gap-6 h-52">
                    {monthly.map((m, i) => {
                      const incomePct = Math.round((m.income / monthlyMax) * 100);
                      const expensePct = Math.round((m.expense / monthlyMax) * 100);
                      return (
                        <div key={`${m.month}-${i}`} className="flex-1 flex flex-col items-center gap-2">
                          <div className="w-full flex-1 flex items-end justify-center gap-2">
                            {/* 收入柱 */}
                            <div className="relative w-1/2 flex-1 flex items-end">
                              <div
                                className="w-full rounded-t-md transition-all duration-500"
                                style={{
                                  height: `${incomePct}%`,
                                  background:
                                    "linear-gradient(to top, #1D4ED8 0%, #3B82F6 60%, #3B82F6 100%)",
                                  boxShadow: "0 0 10px rgba(37, 99, 235, 0.25)",
                                  animationDelay: `${i * 60}ms`,
                                }}
                              />
                              <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] text-ivory-400 whitespace-nowrap">
                                {(m.income / 1000).toFixed(1)}k
                              </div>
                            </div>
                            {/* 支出柱 */}
                            <div className="relative w-1/2 flex-1 flex items-end">
                              <div
                                className="w-full rounded-t-md transition-all duration-500"
                                style={{
                                  height: `${expensePct}%`,
                                  background:
                                    "linear-gradient(to top, #0284C7 0%, #0EA5E9 60%, #0EA5E9 100%)",
                                  boxShadow: "0 0 10px rgba(14, 165, 233, 0.25)",
                                  animationDelay: `${i * 60 + 30}ms`,
                                }}
                              />
                              <div className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] text-terracotta-400/80 whitespace-nowrap">
                                {(m.expense / 1000).toFixed(1)}k
                              </div>
                            </div>
                          </div>
                          <div className="text-[11px] text-ivory-400/60">{m.month}</div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </motion.div>

              {/* 支出明细列表 */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.4 }}
                className="p-6 rounded-2xl bg-gradient-to-br from-brown-800/70 to-charcoal-800/50 border border-gold-500/20 shadow-warm-glow"
              >
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-2">
                    <TrendingDown className="w-4 h-4 text-terracotta-400" />
                    <h3 className="font-serif text-lg text-gold-300">支出明细</h3>
                  </div>
                  <span className="text-xs text-ivory-400/50">
                    合计 <span className="font-serif text-gold-300">¥{totalExpense.toLocaleString()}</span>
                  </span>
                </div>
                {expenses.length === 0 ? (
                  <div className="py-10 text-center text-sm text-ivory-400/50">暂无支出记录</div>
                ) : (
                  <ul className="space-y-3">
                    {expenses.map((e) => {
                      const Icon = getExpenseIcon(e.name);
                      const pct = totalExpense > 0 ? Math.round((e.amount / totalExpense) * 100) : 0;
                      return (
                        <li
                          key={e.name}
                          className="flex items-center gap-3 p-3 rounded-xl bg-charcoal-900/40 border border-brown-700/40 hover:border-gold-500/30 transition"
                        >
                          <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-terracotta-500/10 border border-terracotta-500/25 flex items-center justify-center">
                            <Icon className="w-4 h-4 text-terracotta-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-ivory-500">{e.name}</span>
                              <span className="text-sm font-serif text-gold-300">
                                ¥{e.amount.toLocaleString()}
                              </span>
                            </div>
                            <div className="flex items-center justify-between mt-1.5">
                              <span className="text-[11px] text-ivory-400/50">{e.description || "—"}</span>
                              <span className="text-[11px] text-ivory-400/50">{pct}%</span>
                            </div>
                            {/* 占比条 */}
                            <div className="mt-2 h-1 rounded-full bg-charcoal-900/60 overflow-hidden">
                              <div
                                className="h-full rounded-full"
                                style={{
                                  width: `${pct}%`,
                                  background: "linear-gradient(to right, #0284C7, #0EA5E9)",
                                }}
                              />
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </motion.div>

              {/* 底部 AI 提示 */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4, duration: 0.4 }}
                className="flex items-center gap-2 p-4 rounded-xl bg-gold-500/5 border border-gold-500/20"
              >
                <Sparkles className="w-4 h-4 text-gold-400 flex-shrink-0" />
                <p className="text-xs text-ivory-400/70">
                  本月利润率 {profitMargin}%，净利润 ¥{profit.toLocaleString()}，关注支出结构优化空间。
                </p>
              </motion.div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
