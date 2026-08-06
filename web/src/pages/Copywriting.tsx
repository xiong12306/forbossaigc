import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Tag,
  ShoppingBag,
  Video,
  Loader2,
  Copy,
  Check,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { generateCopywriting as apiGenerate } from "@/api";

// 文案类型配置（value 与后端 copy_type 一致）
const COPY_TYPES = [
  {
    value: "title",
    label: "商品标题",
    desc: "吸睛短标题，突出卖点",
    icon: Tag,
  },
  {
    value: "selling",
    label: "卖点文案",
    desc: "提炼核心卖点，分点展示",
    icon: ShoppingBag,
  },
  {
    value: "xhs",
    label: "小红书种草",
    desc: "口语化种草，氛围感拉满",
    icon: Sparkles,
  },
  {
    value: "script",
    label: "短视频脚本",
    desc: "分镜脚本，节奏紧凑",
    icon: Video,
  },
] as const;

// 风格标签
const STYLES = ["专业带货", "轻松活泼", "高端质感", "性价比"];

type Step = "form" | "generating" | "done" | "error";

export default function Copywriting() {
  const [copyType, setCopyType] = useState<string>("title");
  const [product, setProduct] = useState("");
  const [style, setStyle] = useState<string>("专业带货");
  const [step, setStep] = useState<Step>("form");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState("");
  const [modelUsed, setModelUsed] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState(false);

  // 生成文案
  const handleGenerate = useCallback(async () => {
    if (!product.trim()) return;
    setLoading(true);
    setStep("generating");
    setErrorMsg("");

    try {
      const res = await apiGenerate({
        product: product.trim(),
        copy_type: copyType,
        style,
      });
      setResult(res.content);
      setModelUsed(res.model_used);
      setStep("done");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "生成失败，请重试");
      setStep("error");
    } finally {
      setLoading(false);
    }
  }, [product, copyType, style]);

  // 复制到剪贴板
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }, [result]);

  // 重置
  const handleReset = useCallback(() => {
    setResult("");
    setModelUsed("");
    setStep("form");
    setErrorMsg("");
    setCopied(false);
  }, []);

  const canGenerate = product.trim().length > 0 && !loading;

  const currentTypeLabel = COPY_TYPES.find((t) => t.value === copyType)?.label || "商品标题";

  return (
    <div className="min-h-full p-4 lg:p-6 text-ivory-500">
      <div className="max-w-3xl mx-auto py-4">
          <AnimatePresence mode="wait">
            {/* 表单 / 加载中 */}
            {(step === "form" || step === "generating") && (
              <motion.div
                key="form"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-6"
              >
                {/* 文案类型选择 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    <Sparkles className="w-4 h-4" />
                    文案类型
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {COPY_TYPES.map((t) => {
                      const Icon = t.icon;
                      const active = copyType === t.value;
                      return (
                        <motion.button
                          key={t.value}
                          whileHover={{ scale: 1.03 }}
                          whileTap={{ scale: 0.97 }}
                          onClick={() => setCopyType(t.value)}
                          disabled={loading}
                          className={`relative text-left p-4 rounded-xl border-2 transition-all ${
                            active
                              ? "border-gold-500 bg-gold-500/10 shadow-gold-glow"
                              : "border-brown-700/60 bg-charcoal-900/40 hover:border-gold-500/40"
                          }`}
                        >
                          <Icon
                            className={`w-5 h-5 mb-2 ${active ? "text-gold-300" : "text-ivory-400/70"}`}
                          />
                          <div className={`text-sm font-medium ${active ? "text-gold-300" : "text-ivory-500"}`}>
                            {t.label}
                          </div>
                          <div className="text-[11px] text-ivory-400/50 mt-0.5 leading-snug">{t.desc}</div>
                          {active && (
                            <Check className="absolute top-2 right-2 w-3.5 h-3.5 text-gold-400" />
                          )}
                        </motion.button>
                      );
                    })}
                  </div>
                </div>

                {/* 商品名称 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    <Tag className="w-4 h-4" />
                    商品名称
                  </label>
                  <input
                    type="text"
                    value={product}
                    onChange={(e) => setProduct(e.target.value)}
                    placeholder="如：牛仔裤、保温杯、手机壳..."
                    className="w-full px-4 py-3 rounded-xl bg-brown-800/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/40 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && canGenerate) handleGenerate();
                    }}
                    disabled={loading}
                  />
                </div>

                {/* 风格选择 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    风格偏好
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {STYLES.map((s) => {
                      const active = style === s;
                      return (
                        <button
                          key={s}
                          onClick={() => setStyle(s)}
                          disabled={loading}
                          className={`px-3.5 py-1.5 rounded-full text-xs border transition-all ${
                            active
                              ? "border-gold-500 bg-gold-500/15 text-gold-300"
                              : "border-brown-700/60 text-ivory-400/70 hover:border-gold-500/40"
                          }`}
                        >
                          {s}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 生成按钮 / 加载状态 */}
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-8">
                    <div className="relative w-16 h-16 mb-4">
                      <div className="absolute inset-0 rounded-full border-2 border-gold-500/20" />
                      <Loader2 className="absolute inset-0 m-auto w-8 h-8 text-gold-400 animate-spin" />
                    </div>
                    <div className="font-serif text-lg text-gold-300 mb-1">正在生成文案</div>
                    <div className="text-xs text-ivory-400/50">
                      {product} · {currentTypeLabel}
                    </div>
                  </div>
                ) : (
                  <motion.button
                    whileHover={canGenerate ? { scale: 1.02 } : undefined}
                    whileTap={canGenerate ? { scale: 0.98 } : undefined}
                    onClick={handleGenerate}
                    disabled={!canGenerate}
                    className={`w-full py-4 rounded-full font-medium text-sm transition flex items-center justify-center gap-2 ${
                      canGenerate
                        ? "bg-gold-500 hover:bg-gold-400 text-charcoal-900 shadow-gold-glow"
                        : "bg-brown-800/40 text-ivory-400/30 cursor-not-allowed"
                    }`}
                  >
                    <Sparkles className="w-4 h-4" />
                    生成文案
                  </motion.button>
                )}
              </motion.div>
            )}

            {/* 结果展示 */}
            {step === "done" && (
              <motion.div
                key="done"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-6"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-serif text-2xl text-gold-300">生成完成</h2>
                    <p className="text-sm text-ivory-400/60 mt-1">
                      {product} · {currentTypeLabel} · {style}
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-gold-500/15 text-gold-300 border border-gold-500/30 text-xs flex items-center gap-1">
                    <Sparkles className="w-3 h-3" />
                    {modelUsed.split("/").pop() || modelUsed}
                  </span>
                </div>

                {/* 文案内容卡片 */}
                <div className="relative rounded-2xl border border-gold-500/30 bg-brown-800/40 p-6">
                  <div
                    className="absolute inset-0 rounded-2xl opacity-30 pointer-events-none"
                    style={{
                      background:
                        "radial-gradient(circle at 20% 0%, rgba(37, 99, 235,0.15), transparent 60%)",
                    }}
                  />
                  <div className="relative">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-xs text-gold-400/80 tracking-[0.2em] uppercase">Copy</span>
                      <button
                        onClick={handleCopy}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 transition"
                      >
                        {copied ? (
                          <>
                            <Check className="w-3.5 h-3.5" />
                            已复制
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5" />
                            复制
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-ivory-500">
                      {result}
                    </pre>
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleGenerate}
                    className="flex-1 py-3 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    再生成一条
                  </motion.button>
                  <button
                    onClick={handleCopy}
                    className="flex-1 py-3 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-sm transition flex items-center justify-center gap-2"
                  >
                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    {copied ? "已复制" : "复制文案"}
                  </button>
                </div>

                <button
                  onClick={handleReset}
                  className="w-full py-2.5 text-xs text-ivory-400/50 hover:text-ivory-400 transition"
                >
                  ← 返回重新填写
                </button>
              </motion.div>
            )}

            {/* 错误状态 */}
            {step === "error" && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex flex-col items-center justify-center py-20"
              >
                <div className="w-16 h-16 rounded-full bg-terracotta-500/20 border border-terracotta-500/40 flex items-center justify-center mb-4">
                  <AlertCircle className="w-8 h-8 text-terracotta-300" />
                </div>
                <div className="font-serif text-xl text-terracotta-300 mb-2">生成失败</div>
                <div className="text-sm text-ivory-400/60 mb-6 text-center max-w-md">{errorMsg}</div>
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleGenerate}
                    className="px-6 py-2.5 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 text-sm transition"
                  >
                    重试
                  </motion.button>
                  <button
                    onClick={handleReset}
                    className="px-6 py-2.5 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-sm transition"
                  >
                    重新填写
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
    </div>
  );
}
