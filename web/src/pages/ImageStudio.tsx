import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Package,
  Image as ImageIcon,
  Sparkles,
  Loader2,
  Download,
  RefreshCw,
  Check,
  ChevronRight,
  Wand2,
} from "lucide-react";
import { chat as apiChat, reset as apiReset } from "@/api";
import type { Artifact } from "@/types";

// 图片类型配置
const IMAGE_TYPES = [
  { value: "main", label: "商品主图", desc: "白底/纯色背景，突出商品主体", icon: "📦" },
  { value: "detail", label: "产品详情图", desc: "多角度展示，细节卖点清晰", icon: "🔍" },
  { value: "scene", label: "场景图", desc: "生活化场景，氛围感强", icon: "🏠" },
  { value: "poster", label: "营销海报", desc: "促销活动风格，留白放文案", icon: "🎨" },
  { value: "carousel", label: "轮播图", desc: "统一风格系列，适合首页", icon: "🔄" },
] as const;

const QUANTITIES = [1, 2, 4, 6];

const STYLES = [
  "轻奢暖色调", "极简白底", "ins风", "国风", "复古", "日系清新", "高级感", "时尚活泼",
];

type Step = "form" | "confirming" | "generating" | "done" | "error";

export default function ImageStudio() {
  const [product, setProduct] = useState("");
  const [imageType, setImageType] = useState<string>("main");
  const [quantity, setQuantity] = useState<number>(2);
  const [style, setStyle] = useState<string>("");
  const [extraDesc, setExtraDesc] = useState("");
  const [step, setStep] = useState<Step>("form");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [progressText, setProgressText] = useState("");

  // 构建发送给后端的指令
  const buildCommand = useCallback(() => {
    const typeLabel = IMAGE_TYPES.find((t) => t.value === imageType)?.label || "主图";
    let cmd = `给${product}出${quantity}张${typeLabel}`;
    if (style) cmd += `，${style}`;
    if (extraDesc) cmd += `，${extraDesc}`;
    return cmd;
  }, [product, imageType, quantity, style, extraDesc]);

  // 执行出图：发送指令 → 自动确认 → 获取结果
  const handleGenerate = useCallback(async () => {
    if (!product.trim()) return;
    setStep("confirming");
    setProgressText("正在分析任务...");
    setErrorMsg("");

    try {
      // 1. 发送出图指令
      const cmd = buildCommand();
      const res1 = await apiChat(cmd, sessionId ?? undefined);
      setSessionId(res1.session_id);

      if (res1.status === "awaiting_confirmation" && res1.summary) {
        setStep("generating");
        setProgressText(`已确认：${res1.message}`);

        // 2. 自动发送确认（带修改参数一步完成）
        const defaultType = (res1.summary.params.image_type as string) || "main";
        const defaultQty = Number(res1.summary.params.quantity) || 1;
        const typeNames: Record<string, string> = {
          main: "商品主图", detail: "产品详情图", scene: "场景图",
          poster: "营销海报", carousel: "轮播图",
        };

        const parts: string[] = [];
        if (imageType !== defaultType) parts.push(`类型改成${typeNames[imageType]}`);
        if (quantity !== defaultQty) parts.push(`数量改成${quantity}张`);
        const confirmMsg = parts.length > 0 ? `${parts.join("，")}，确认` : "确认";

        setProgressText("正在生成图片...");
        const res2 = await apiChat(confirmMsg, res1.session_id);

        if (res2.artifacts && res2.artifacts.length > 0) {
          setArtifacts(res2.artifacts);
          setStep("done");
          setProgressText("");
        } else if (res2.status === "executing") {
          // 真实平台可能需要轮询，这里等待后端返回
          setProgressText("图片生成中，请稍候...");
          setStep("generating");
        } else {
          setStep("done");
          setArtifacts(res2.artifacts || []);
        }
      } else if (res1.artifacts && res1.artifacts.length > 0) {
        // 某些情况直接返回结果
        setArtifacts(res1.artifacts);
        setStep("done");
      } else {
        setErrorMsg(res1.message || "无法识别任务，请补充商品名称");
        setStep("error");
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "生成失败，请重试");
      setStep("error");
    }
  }, [buildCommand, product, imageType, quantity, sessionId]);

  // 重置表单
  const handleReset = useCallback(async () => {
    if (sessionId) {
      try { await apiReset(sessionId); } catch { /* ignore */ }
    }
    setSessionId(null);
    setArtifacts([]);
    setStep("form");
    setErrorMsg("");
    setProgressText("");
  }, [sessionId]);

  const canGenerate = product.trim().length > 0 && step === "form";

  return (
    <div className="min-h-full flex flex-col bg-charcoal-900 text-ivory-500">
      {/* 页面标题 */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gold-500/15">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center">
            <Wand2 className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="font-serif text-xl text-gold-400">出图中心</div>
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-3xl mx-auto">
          <AnimatePresence mode="wait">
            {/* 步骤1：填写表单 */}
            {step === "form" && (
              <motion.div
                key="form"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="space-y-6"
              >
                {/* 商品名称 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    <Package className="w-4 h-4" />
                    商品名称
                  </label>
                  <input
                    type="text"
                    value={product}
                    onChange={(e) => setProduct(e.target.value)}
                    placeholder="如：牛仔裤、保温杯、手机壳..."
                    className="w-full px-4 py-3 rounded-xl bg-brown-800/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/40 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition"
                    onKeyDown={(e) => { if (e.key === "Enter" && canGenerate) handleGenerate(); }}
                  />
                </div>

                {/* 图片类型 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    <ImageIcon className="w-4 h-4" />
                    图片类型
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {IMAGE_TYPES.map((type) => (
                      <motion.button
                        key={type.value}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => setImageType(type.value)}
                        className={`relative text-left p-4 rounded-xl border-2 transition-all ${
                          imageType === type.value
                            ? "border-gold-500 bg-gold-500/10 shadow-gold-glow"
                            : "border-brown-700/60 bg-charcoal-900/40 hover:border-gold-500/40"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <span className="text-2xl">{type.icon}</span>
                          <div className="flex-1">
                            <div className={`text-sm font-medium ${imageType === type.value ? "text-gold-300" : "text-ivory-500"}`}>
                              {type.label}
                            </div>
                            <div className="text-xs text-ivory-400/50 mt-0.5">{type.desc}</div>
                          </div>
                          {imageType === type.value && (
                            <Check className="w-4 h-4 text-gold-400 flex-shrink-0 mt-0.5" />
                          )}
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* 生成数量 */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    <Sparkles className="w-4 h-4" />
                    生成数量
                  </label>
                  <div className="flex gap-3">
                    {QUANTITIES.map((qty) => (
                      <motion.button
                        key={qty}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => setQuantity(qty)}
                        className={`flex-1 py-3 rounded-xl text-sm font-medium border-2 transition-all ${
                          quantity === qty
                            ? "border-gold-500 bg-gold-500/20 text-gold-300"
                            : "border-brown-700/60 bg-charcoal-900/40 text-ivory-400/70 hover:border-gold-500/40"
                        }`}
                      >
                        {qty} 张
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* 风格选择（可选） */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    风格偏好 <span className="text-ivory-400/40 text-xs">（可选）</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {STYLES.map((s) => (
                      <button
                        key={s}
                        onClick={() => setStyle(style === s ? "" : s)}
                        className={`px-3 py-1.5 rounded-full text-xs border transition-all ${
                          style === s
                            ? "border-gold-500 bg-gold-500/15 text-gold-300"
                            : "border-brown-700/60 text-ivory-400/70 hover:border-gold-500/40"
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 额外描述（可选） */}
                <div>
                  <label className="flex items-center gap-2 mb-3 text-sm text-gold-300 font-medium">
                    补充描述 <span className="text-ivory-400/40 text-xs">（可选）</span>
                  </label>
                  <textarea
                    value={extraDesc}
                    onChange={(e) => setExtraDesc(e.target.value)}
                    placeholder="如：户外阳光场景、模特穿着展示、桌面摆拍..."
                    rows={2}
                    className="w-full px-4 py-3 rounded-xl bg-brown-800/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/40 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition resize-none"
                  />
                </div>

                {/* 生成按钮 */}
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
                  开始生成 {IMAGE_TYPES.find(t => t.value === imageType)?.label} × {quantity}张
                </motion.button>
              </motion.div>
            )}

            {/* 步骤2：确认/生成中 */}
            {(step === "confirming" || step === "generating") && (
              <motion.div
                key="loading"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex flex-col items-center justify-center py-20"
              >
                <div className="relative w-20 h-20 mb-6">
                  <div className="absolute inset-0 rounded-full border-2 border-gold-500/20" />
                  <div className="absolute inset-0 rounded-full border-2 border-gold-500 border-t-transparent animate-spin" />
                  <Loader2 className="absolute inset-0 m-auto w-8 h-8 text-gold-400 animate-pulse" />
                </div>
                <div className="font-serif text-xl text-gold-300 mb-2">正在生成图片</div>
                <div className="text-sm text-ivory-400/60">{progressText}</div>
                <div className="mt-4 text-xs text-ivory-400/40">
                  商品：{product} · {IMAGE_TYPES.find(t => t.value === imageType)?.label} × {quantity}张
                </div>
              </motion.div>
            )}

            {/* 步骤3：结果展示 */}
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
                      {product} · {IMAGE_TYPES.find(t => t.value === imageType)?.label} · {artifacts.length}张
                    </p>
                  </div>
                  <span className="px-3 py-1 rounded-full bg-gold-500/15 text-gold-300 border border-gold-500/30 text-xs">
                    ✓ 完成
                  </span>
                </div>

                {/* 图片网格 */}
                {artifacts.length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    {artifacts.map((artifact, i) => {
                      const isRealImage = artifact.kind === "IMAGE" &&
                        artifact.url_or_path &&
                        artifact.url_or_path.startsWith("http");
                      return (
                        <motion.div
                          key={artifact.artifact_id}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: 0.1 * i, type: "spring", stiffness: 200, damping: 20 }}
                          whileHover={{ scale: 1.03 }}
                          className="group relative aspect-square rounded-xl overflow-hidden border border-gold-500/30 bg-gradient-to-br from-brown-700 via-charcoal-800 to-brown-800"
                        >
                          {isRealImage ? (
                            <img
                              src={artifact.url_or_path!}
                              alt={`Generated ${i + 1}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          ) : (
                            <div className="relative h-full flex flex-col items-center justify-center gap-2">
                              <div
                                className="absolute inset-0 opacity-30"
                                style={{
                                  background: "radial-gradient(circle at 30% 30%, rgba(201,169,97,0.4), transparent 60%)",
                                }}
                              />
                              <ImageIcon className="w-8 h-8 text-gold-400 relative" />
                              <div className="text-[10px] text-ivory-400/60 relative">Mock 占位图</div>
                              <div className="text-[10px] text-gold-300/80 font-mono relative">
                                #{artifact.artifact_id.slice(-8)}
                              </div>
                            </div>
                          )}
                          {/* 序号 */}
                          <div className="absolute top-2 left-2 w-6 h-6 rounded-full bg-black/50 backdrop-blur flex items-center justify-center text-[10px] text-gold-300 font-medium">
                            {i + 1}
                          </div>
                          {/* 下载按钮（真实图片才显示） */}
                          {isRealImage && (
                            <a
                              href={artifact.url_or_path!}
                              download
                              target="_blank"
                              rel="noopener noreferrer"
                              className="absolute bottom-2 right-2 w-8 h-8 rounded-lg bg-black/50 backdrop-blur flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                            >
                              <Download className="w-4 h-4 text-gold-300" />
                            </a>
                          )}
                        </motion.div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12 text-ivory-400/50">
                    暂无图片产出
                  </div>
                )}

                {/* 操作按钮 */}
                <div className="flex gap-3">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleReset}
                    className="flex-1 py-3 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    再生成一组
                  </motion.button>
                  <a
                    href="/"
                    className="flex-1 py-3 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-sm transition flex items-center justify-center gap-2"
                  >
                    <ChevronRight className="w-4 h-4" />
                    返回助手
                  </a>
                </div>
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
                  <span className="text-2xl">⚠️</span>
                </div>
                <div className="font-serif text-xl text-terracotta-300 mb-2">生成失败</div>
                <div className="text-sm text-ivory-400/60 mb-6 text-center max-w-md">{errorMsg}</div>
                <button
                  onClick={handleReset}
                  className="px-6 py-2.5 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-sm transition"
                >
                  重新填写
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
