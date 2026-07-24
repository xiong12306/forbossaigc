import { useState } from "react";
import { motion } from "framer-motion";
import { Check, Image as ImageIcon, Layers, ShoppingBag, Megaphone, Film } from "lucide-react";
import type { Summary } from "@/types";

export interface ImageTypeOption {
  value: string;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const IMAGE_TYPES: ImageTypeOption[] = [
  {
    value: "main",
    label: "商品主图",
    description: "突出主体，提升点击率",
    icon: <ShoppingBag className="w-5 h-5" />,
  },
  {
    value: "detail",
    label: "产品详情图",
    description: "展示卖点细节，引导下单",
    icon: <Layers className="w-5 h-5" />,
  },
  {
    value: "scene",
    label: "场景图",
    description: "真实使用场景，代入感强",
    icon: <ImageIcon className="w-5 h-5" />,
  },
  {
    value: "poster",
    label: "营销海报",
    description: "视觉冲击力，促销氛围",
    icon: <Megaphone className="w-5 h-5" />,
  },
  {
    value: "carousel",
    label: "轮播图",
    description: "多角度展示，适合首页",
    icon: <Film className="w-5 h-5" />,
  },
];

const QUANTITY_OPTIONS = [1, 2, 4, 6];

interface SelectedTypes {
  [key: string]: number;
}

interface Props {
  summary: Summary;
  onConfirm: (selected: SelectedTypes) => void;
  onCancel: () => void;
}

/**
 * 图片类型选择器（参考无量AI第一步界面）
 * 支持选择多种图片类型，每种类型设置生成数量
 */
export default function ImageTypeSelector({ summary, onConfirm, onCancel }: Props) {
  const [selected, setSelected] = useState<SelectedTypes>(() => {
    const initial: SelectedTypes = {};
    const defaultType = summary.params.image_type as string || "main";
    const defaultQty = (summary.params.quantity as number) || 1;
    initial[defaultType] = defaultQty;
    return initial;
  });

  const toggleType = (typeValue: string) => {
    setSelected((prev) => {
      const next = { ...prev };
      if (typeValue in next) {
        delete next[typeValue];
      } else {
        next[typeValue] = 1;
      }
      return next;
    });
  };

  const setQuantity = (typeValue: string, qty: number) => {
    setSelected((prev) => ({
      ...prev,
      [typeValue]: qty,
    }));
  };

  const totalCount = Object.values(selected).reduce((sum, q) => sum + q, 0);
  const hasSelection = Object.keys(selected).length > 0;

  const handleConfirm = () => {
    if (!hasSelection) return;
    onConfirm(selected);
  };

  return (
    <div className="space-y-4">
      <div className="text-center">
        <h4 className="text-lg font-serif text-gold-300 mb-1">选择图片类型</h4>
        <p className="text-xs text-ivory-400/60">请勾选需要生成的图片类型和数量</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {IMAGE_TYPES.map((type) => {
          const isSelected = type.value in selected;
          const qty = selected[type.value] || 1;

          return (
            <motion.div
              key={type.value}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => toggleType(type.value)}
              className={`relative rounded-xl border-2 p-4 cursor-pointer transition-all ${
                isSelected
                  ? "border-gold-500 bg-gold-500/10 shadow-gold-glow"
                  : "border-brown-700/60 bg-charcoal-900/40 hover:border-gold-500/40"
              }`}
            >
              {/* 选中标记 */}
              {isSelected && (
                <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-gold-500 flex items-center justify-center">
                  <Check className="w-3 h-3 text-charcoal-900" />
                </div>
              )}

              <div className="flex items-start gap-3">
                <div
                  className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                    isSelected ? "bg-gold-500/20 text-gold-400" : "bg-brown-800/60 text-ivory-400/60"
                  }`}
                >
                  {type.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <h5 className="font-medium text-ivory-500">{type.label}</h5>
                  <p className="text-xs text-ivory-400/50 mt-0.5">{type.description}</p>
                </div>
              </div>

              {/* 数量选择 */}
              {isSelected && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  className="mt-3 pt-3 border-t border-gold-500/20"
                >
                  <div className="text-[10px] text-ivory-400/50 mb-2 tracking-wider">生成数量</div>
                  <div className="flex gap-1.5 flex-wrap">
                    {QUANTITY_OPTIONS.map((q) => (
                      <button
                        key={q}
                        onClick={(e) => {
                          e.stopPropagation();
                          setQuantity(type.value, q);
                        }}
                        className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                          qty === q
                            ? "bg-gold-500 text-charcoal-900"
                            : "bg-brown-800/80 text-ivory-400/70 hover:bg-brown-700/80"
                        }`}
                      >
                        {q}张
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* 底部操作栏 */}
      <div className="flex gap-2 pt-2">
        <button
          onClick={onCancel}
          className="flex-1 py-2.5 rounded-full border border-brown-700/60 text-ivory-400/70 hover:bg-brown-800/40 text-sm transition"
        >
          取消
        </button>
        <motion.button
          whileHover={{ scale: hasSelection ? 1.02 : 1 }}
          whileTap={{ scale: hasSelection ? 0.98 : 1 }}
          onClick={handleConfirm}
          disabled={!hasSelection}
          className={`flex-[2] py-2.5 rounded-full font-medium text-sm transition flex items-center justify-center gap-1.5 ${
            hasSelection
              ? "bg-gold-500 hover:bg-gold-400 text-charcoal-900 shadow-gold-glow"
              : "bg-brown-800/60 text-ivory-400/40 cursor-not-allowed"
          }`}
        >
          <Check className="w-4 h-4" /> 确认生成 {totalCount > 0 ? `(${totalCount}张)` : ""}
        </motion.button>
      </div>
    </div>
  );
}

export type { SelectedTypes };
