import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Check,
  Pencil,
  X,
  AlertTriangle,
  Clock,
  Coins,
  Package,
  Image as ImageIcon,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import type { Summary } from "@/types";
import ImageTypeSelector, { type SelectedTypes } from "./ImageTypeSelector";

interface Props {
  summary: Summary;
  onConfirm: (selectedTypes?: SelectedTypes) => void;
  onModify: () => void;
  onCancel: () => void;
}

const IMAGE_TYPE_NAMES: Record<string, string> = {
  main: "商品主图",
  detail: "产品详情图",
  scene: "场景图",
  poster: "营销海报",
  carousel: "轮播图",
};

const QUICK_QTYS = [1, 2, 4, 6];

export default function SummaryCard({ summary, onConfirm, onModify, onCancel }: Props) {
  const [showFullSelector, setShowFullSelector] = useState(false);
  const [selectedType, setSelectedType] = useState<string>(
    (summary.params.image_type as string) || "main"
  );
  const [selectedQty, setSelectedQty] = useState<number>(
    (summary.params.quantity as number) || 1
  );

  const paramEntries = Object.entries(summary.params || {}).filter(
    ([k]) => !["image_type", "quantity"].includes(k)
  );

  const defaultType = (summary.params.image_type as string) || "main";
  const defaultQty = Number(summary.params.quantity) || 1;
  const baseDuration = Number(summary.estimated_duration_sec) || 30;
  const baseCost = Number(summary.estimated_cost) || 2;
  const totalQty = selectedQty;
  const scaledDuration = Math.round((baseDuration * totalQty) / defaultQty);
  const scaledCost = Math.round((baseCost * totalQty) / defaultQty);
  const isHighCost = scaledCost > 20;

  const handleFinalConfirm = () => {
    onConfirm({ [selectedType]: selectedQty });
  };

  if (showFullSelector) {
    return (
      <motion.div
        initial={{ opacity: 0, x: 40 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 40 }}
        transition={{ type: "spring", stiffness: 240, damping: 22 }}
        className="relative bg-brown-800/70 backdrop-blur border border-gold-500/20 rounded-2xl overflow-hidden shadow-warm-glow"
      >
        <div className="h-1 bg-gradient-to-r from-gold-600 via-gold-400 to-terracotta-500" />
        <div className="p-5">
          <ImageTypeSelector
            summary={summary}
            onConfirm={(selected) => {
              const entries = Object.entries(selected);
              if (entries.length > 0) {
                setSelectedType(entries[0][0]);
                setSelectedQty(entries[0][1]);
              }
              setShowFullSelector(false);
            }}
            onCancel={() => setShowFullSelector(false)}
          />
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      transition={{ type: "spring", stiffness: 240, damping: 22 }}
      className="relative bg-brown-800/70 backdrop-blur border border-gold-500/20 rounded-2xl overflow-hidden shadow-warm-glow"
    >
      <div className="h-1 bg-gradient-to-r from-gold-600 via-gold-400 to-terracotta-500" />
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-xl text-gold-300">任务摘要</h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-gold-500/15 text-gold-300 border border-gold-500/30 tracking-wider">
            {summary.task_type === "image_gen" ? "电商出图" : summary.task_type}
          </span>
        </div>

        {/* 商品 */}
        <div className="flex items-center gap-2 mb-4 text-sm">
          <Package className="w-4 h-4 text-gold-400 flex-shrink-0" />
          <span className="text-ivory-400/60">商品</span>
          <span className="text-ivory-500 font-medium text-lg">
            {summary.product || "未指定"}
          </span>
        </div>

        {/* 图片类型快速选择 */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2 text-sm">
            <ImageIcon className="w-4 h-4 text-gold-400 flex-shrink-0" />
            <span className="text-ivory-400/60">图片类型</span>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            {Object.entries(IMAGE_TYPE_NAMES).map(([type, name]) => (
              <motion.button
                key={type}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setSelectedType(type)}
                className={`py-2 px-2 rounded-lg text-xs border transition-all ${
                  selectedType === type
                    ? "border-gold-500 bg-gold-500/15 text-gold-300 shadow-gold-glow"
                    : "border-brown-700/60 bg-charcoal-900/40 text-ivory-400/70 hover:border-gold-500/40"
                }`}
              >
                {name}
              </motion.button>
            ))}
          </div>

          {/* 数量选择 */}
          <div className="flex items-center gap-2 mb-2 text-sm">
            <span className="text-ivory-400/60 text-xs">生成数量</span>
          </div>
          <div className="flex gap-2">
            {QUICK_QTYS.map((qty) => (
              <motion.button
                key={qty}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setSelectedQty(qty)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all ${
                  selectedQty === qty
                    ? "border-gold-500 bg-gold-500/20 text-gold-300"
                    : "border-brown-700/60 bg-charcoal-900/40 text-ivory-400/70 hover:border-gold-500/40"
                }`}
              >
                {qty}张
              </motion.button>
            ))}
          </div>
        </div>

        {/* 耗时 & 积分 */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="rounded-lg bg-charcoal-900/60 border border-brown-700/60 p-2.5">
            <div className="flex items-center gap-1.5 text-[10px] text-ivory-400/50 tracking-widest mb-1">
              <Clock className="w-3 h-3" /> 预估耗时
            </div>
            <div className="text-sm text-ivory-500">
              ~{scaledDuration}s
            </div>
          </div>
          <div
            className={`rounded-lg p-2.5 border ${
              isHighCost
                ? "bg-terracotta-500/10 border-terracotta-500/40"
                : "bg-charcoal-900/60 border-brown-700/60"
            }`}
          >
            <div
              className={`flex items-center gap-1.5 text-[10px] tracking-widest mb-1 ${
                isHighCost ? "text-terracotta-400" : "text-ivory-400/50"
              }`}
            >
              <Coins className="w-3 h-3" /> 预估积分
            </div>
            <div
              className={`text-sm font-medium ${
                isHighCost ? "text-terracotta-400" : "text-ivory-500"
              }`}
            >
              {scaledCost}
            </div>
          </div>
        </div>

        {/* 高成本警告 */}
        {isHighCost && (
          <div className="flex items-center gap-2 mb-4 px-3 py-2 rounded-lg bg-terracotta-500/10 border border-terracotta-500/30 text-xs text-terracotta-300">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            数量较多，积分消耗较大
          </div>
        )}

        {/* 按钮组 */}
        <div className="flex flex-col gap-2">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleFinalConfirm}
            className="w-full py-3 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-1.5"
          >
            <Check className="w-4 h-4" /> 开始生成 {IMAGE_TYPE_NAMES[selectedType]} × {totalQty}张
          </motion.button>
          <div className="flex gap-2">
            <button
              onClick={onModify}
              className="flex-1 py-2 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-xs transition flex items-center justify-center gap-1.5"
            >
              <Pencil className="w-3 h-3" /> 文字补充需求
            </button>
            <button
              onClick={onCancel}
              className="flex-1 py-2 rounded-full text-ivory-400/60 hover:text-red-300 hover:bg-red-500/10 text-xs transition flex items-center justify-center gap-1.5"
            >
              <X className="w-3 h-3" /> 取消
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
