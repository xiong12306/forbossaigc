import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Headphones,
  MessageSquare,
  Clock,
  Smile,
  ChevronDown,
  Bot,
  Settings2,
  Circle,
  Check,
  Loader2,
} from "lucide-react";
import { serviceApi } from "@/platformApi";

// 头像渐变色（按索引轮转，保持暖调轻奢风格）
const AVATAR_GRADIENTS = [
  "from-gold-500 to-terracotta-500",
  "from-terracotta-400 to-brown-700",
  "from-gold-400 to-gold-600",
  "from-brown-700 to-charcoal-900",
  "from-ivory-400 to-gold-500",
  "from-gold-300 to-terracotta-400",
];

interface Message {
  id: number;
  customer_name: string;
  message_preview: string;
  unread_count: number;
  status: "pending" | "resolved";
  created_at: string;
  updated_at?: string;
}

interface FAQ {
  id: number;
  question: string;
  answer: string;
  category?: string;
  sort_order?: number;
  created_at?: string;
}

// 相对时间格式化
function formatRelativeTime(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (isNaN(date.getTime())) return iso;
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  if (diffMs < 0) return "刚刚";
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 30) return `${diffDay}天前`;
  return date.toLocaleDateString("zh-CN");
}

export default function Service() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [smartReplyOn, setSmartReplyOn] = useState(true);
  const [activeChat, setActiveChat] = useState<number | null>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  const loadMessages = async () => {
    try {
      const data = await serviceApi.messages();
      setMessages(data ?? []);
    } catch (err) {
      console.error("加载消息失败:", err);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [msgs, fqs] = await Promise.all([
          serviceApi.messages(),
          serviceApi.faq(),
        ]);
        if (cancelled) return;
        setMessages(msgs ?? []);
        setFaqs(fqs ?? []);
        if (msgs && msgs.length > 0) setActiveChat(msgs[0].id);
        if (fqs && fqs.length > 0) setOpenFaq(fqs[0].id);
      } catch (err) {
        console.error("加载客服数据失败:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // 标记已处理
  const handleResolve = async (id: number) => {
    setResolvingId(id);
    try {
      await serviceApi.resolveMessage(id);
      await loadMessages();
    } catch (err) {
      console.error("标记已处理失败:", err);
    } finally {
      setResolvingId(null);
    }
  };

  // 顶部统计：今日消息数=消息总数，其余静态
  const todayMsgCount = messages.length;
  const STATS = [
    {
      key: "msg",
      label: "今日消息数",
      value: String(todayMsgCount),
      unit: "条",
      icon: MessageSquare,
      gradient: "from-gold-500 to-gold-300",
      delta: "+12%",
    },
    {
      key: "resp",
      label: "平均响应时间",
      value: "1.8",
      unit: "分钟",
      icon: Clock,
      gradient: "from-terracotta-500 to-gold-400",
      delta: "-15%",
    },
    {
      key: "satisfaction",
      label: "满意度",
      value: "96",
      unit: "%",
      icon: Smile,
      gradient: "from-brown-700 to-gold-500",
      delta: "+3%",
    },
  ] as const;

  return (
    <div className="min-h-full p-4 lg:p-6 text-ivory-500">
      <div className="max-w-7xl mx-auto">
        {/* 统计卡片 */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          {STATS.map((s, idx) => {
            const Icon = s.icon;
            return (
              <motion.div
                key={s.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: idx * 0.06 }}
                className="relative p-5 rounded-2xl bg-charcoal-800/60 border border-brown-700/40 hover:border-gold-500/40 transition overflow-hidden"
              >
                <div
                  className="absolute -top-6 -right-6 w-24 h-24 rounded-full bg-gradient-to-br opacity-10 blur-2xl pointer-events-none"
                  style={{ background: "radial-gradient(circle, rgba(37, 99, 235,0.6), transparent 70%)" }}
                />
                <div className="flex items-center justify-between">
                  <div
                    className={`w-10 h-10 rounded-lg bg-gradient-to-br ${s.gradient} flex items-center justify-center`}
                  >
                    <Icon className="w-5 h-5 text-charcoal-900" />
                  </div>
                  <span className="text-xs text-gold-300/80">{s.delta}</span>
                </div>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="font-serif text-3xl text-ivory-500">{s.value}</span>
                  <span className="text-xs text-ivory-400/50">{s.unit}</span>
                </div>
                <div className="text-xs text-ivory-400/60 mt-1">{s.label}</div>
              </motion.div>
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
            {/* 主体：左右分栏 */}
            <div className="flex flex-col lg:flex-row gap-6 mb-8">
              {/* 左侧：待处理消息 */}
              <section className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-serif text-xl text-gold-300 flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" />
                    今日待处理消息
                  </h2>
                  <span className="text-xs text-ivory-400/50">{messages.length} 条会话</span>
                </div>

                {messages.length === 0 ? (
                  <div className="px-5 py-10 rounded-xl bg-charcoal-800/60 border border-brown-700/40 text-center text-sm text-ivory-400/50">
                    暂无消息
                  </div>
                ) : (
                  <div className="space-y-2">
                    {messages.map((c, idx) => {
                      const isActive = activeChat === c.id;
                      const gradient =
                        AVATAR_GRADIENTS[idx % AVATAR_GRADIENTS.length];
                      const isPending = c.status === "pending";
                      const isResolving = resolvingId === c.id;
                      return (
                        <motion.div
                          key={c.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.3, delay: idx * 0.05 }}
                          onClick={() => setActiveChat(c.id)}
                          className={`flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition ${
                            isActive
                              ? "border-gold-500 bg-gold-500/10"
                              : "border-brown-700/40 bg-charcoal-800/60 hover:border-gold-500/40"
                          }`}
                        >
                          {/* 头像 */}
                          <div className="relative flex-shrink-0">
                            <div
                              className={`w-11 h-11 rounded-full bg-gradient-to-br ${gradient} flex items-center justify-center font-serif text-base text-charcoal-900`}
                            >
                              {c.customer_name?.charAt(0) ?? "?"}
                            </div>
                            {c.unread_count > 0 && (
                              <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-terracotta-500 flex items-center justify-center text-[10px] text-white font-medium">
                                {c.unread_count}
                              </span>
                            )}
                          </div>
                          {/* 消息内容 */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-ivory-500 font-medium truncate">
                                {c.customer_name}
                              </span>
                              <span className="text-xs text-ivory-400/40 flex-shrink-0 ml-2">
                                {formatRelativeTime(c.updated_at || c.created_at)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <p className="text-xs text-ivory-400/60 truncate">
                                {c.message_preview}
                              </p>
                            </div>
                          </div>
                          {/* 状态标识 / 操作按钮 */}
                          {isPending ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (!isResolving) handleResolve(c.id);
                              }}
                              disabled={isResolving}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 transition flex-shrink-0 disabled:opacity-60"
                            >
                              {isResolving ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Check className="w-3 h-3" />
                              )}
                              标记已处理
                            </button>
                          ) : (
                            <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs border border-brown-700/60 text-ivory-400/50 flex-shrink-0">
                              <Check className="w-3 h-3" />
                              已处理
                            </span>
                          )}
                          {isPending && c.unread_count > 0 && (
                            <Circle className="w-2 h-2 fill-terracotta-500 text-terracotta-500 flex-shrink-0" />
                          )}
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* 右侧：FAQ 列表 */}
              <section className="w-full lg:w-[420px] flex-shrink-0">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="font-serif text-xl text-gold-300 flex items-center gap-2">
                    <Headphones className="w-4 h-4" />
                    常见问题
                  </h2>
                  <span className="text-xs text-ivory-400/50">FAQ</span>
                </div>

                {faqs.length === 0 ? (
                  <div className="px-5 py-10 rounded-xl bg-charcoal-800/60 border border-brown-700/40 text-center text-sm text-ivory-400/50">
                    暂无常见问题
                  </div>
                ) : (
                  <div className="space-y-2">
                    {faqs.map((f, idx) => {
                      const open = openFaq === f.id;
                      return (
                        <motion.div
                          key={f.id}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.25, delay: idx * 0.04 }}
                          className="rounded-xl bg-charcoal-800/60 border border-brown-700/40 hover:border-gold-500/40 transition overflow-hidden"
                        >
                          <button
                            onClick={() => setOpenFaq(open ? null : f.id)}
                            className="w-full flex items-center justify-between px-4 py-3 text-left"
                          >
                            <span className="text-sm text-ivory-500 font-medium pr-3">
                              {f.question}
                            </span>
                            <motion.span
                              animate={{ rotate: open ? 180 : 0 }}
                              transition={{ duration: 0.2 }}
                            >
                              <ChevronDown
                                className={`w-4 h-4 flex-shrink-0 ${
                                  open ? "text-gold-300" : "text-ivory-400/40"
                                }`}
                              />
                            </motion.span>
                          </button>
                          <AnimatePresence initial={false}>
                            {open && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.25 }}
                                className="overflow-hidden"
                              >
                                <div className="px-4 pb-4 text-xs leading-relaxed text-ivory-400/70 border-t border-brown-700/40 pt-3">
                                  {f.answer}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>

            {/* 底部：智能回复 + 自动回复规则 */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* 智能回复开关 */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className="flex items-center justify-between p-5 rounded-2xl bg-charcoal-800/60 border border-brown-700/40"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center">
                    <Bot className="w-5 h-5 text-charcoal-900" />
                  </div>
                  <div>
                    <div className="text-sm text-ivory-500 font-medium">智能回复助手</div>
                    <div className="text-xs text-ivory-400/50 mt-0.5">
                      AI 自动识别意图，秒级响应客户咨询
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setSmartReplyOn(!smartReplyOn)}
                  className={`relative w-12 h-6 rounded-full transition ${
                    smartReplyOn ? "bg-gold-500" : "bg-brown-700"
                  }`}
                >
                  <motion.span
                    layout
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className={`absolute top-0.5 w-5 h-5 rounded-full bg-ivory-500 shadow-md ${
                      smartReplyOn ? "left-6" : "left-0.5"
                    }`}
                  />
                </button>
              </motion.div>

              {/* 自动回复规则入口 */}
              <motion.button
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.05 }}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.99 }}
                className="flex items-center justify-between p-5 rounded-2xl bg-charcoal-800/60 border border-brown-700/40 hover:border-gold-500/40 transition text-left"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-brown-700 to-gold-500 flex items-center justify-center">
                    <Settings2 className="w-5 h-5 text-charcoal-900" />
                  </div>
                  <div>
                    <div className="text-sm text-ivory-500 font-medium">自动回复规则设置</div>
                    <div className="text-xs text-ivory-400/50 mt-0.5">
                      自定义触发关键词与回复内容
                    </div>
                  </div>
                </div>
                <span className="text-xs text-gold-300">配置 →</span>
              </motion.button>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
