import { motion } from "framer-motion";
import { Check, X } from "lucide-react";
import type { TimelineNode } from "@/types";

interface Props {
  timeline: TimelineNode[];
  /** 水平排布（移动端顶部用） */
  horizontal?: boolean;
}

// 初始空态时间线节点
const DEFAULT_TIMELINE: TimelineNode[] = [
  { label: "理解指令", status: "pending" },
  { label: "确认任务", status: "pending" },
  { label: "执行生成", status: "pending" },
  { label: "交付产出", status: "pending" },
  { label: "验收归档", status: "pending" },
];

/**
 * 左侧状态时间线：5 个节点，琥珀金高亮 active
 */
export default function Timeline({ timeline, horizontal = false }: Props) {
  const nodes = timeline.length > 0 ? timeline : DEFAULT_TIMELINE;

  if (horizontal) {
    // 水平紧凑模式（移动端顶部）
    return (
      <div className="flex items-center gap-1 overflow-x-auto py-1">
        {nodes.map((node, i) => {
          const isActive = node.status === "active";
          const isDone = node.status === "done";
          const isCancelled = node.status === "cancelled";
          return (
            <motion.div
              key={node.label + i}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
              className="flex items-center gap-1 flex-shrink-0"
            >
              <div
                className={`w-4 h-4 rounded-full flex items-center justify-center border text-[8px] ${
                  isDone
                    ? "bg-gold-500 border-gold-500 text-charcoal-900"
                    : isActive
                    ? "bg-charcoal-900 border-gold-500 text-gold-400"
                    : isCancelled
                    ? "bg-charcoal-900 border-red-500/60 text-red-400"
                    : "bg-charcoal-900 border-brown-700 text-ivory-400/40"
                }`}
              >
                {isDone ? (
                  <Check className="w-2 h-2" />
                ) : isCancelled ? (
                  <X className="w-2 h-2" />
                ) : null}
              </div>
              <span
                className={`text-[10px] whitespace-nowrap ${
                  isActive
                    ? "text-gold-300"
                    : isDone
                    ? "text-ivory-400/80"
                    : isCancelled
                    ? "text-red-400/70 line-through"
                    : "text-ivory-400/40"
                }`}
              >
                {node.label}
              </span>
              {i < nodes.length - 1 && (
                <span className="text-ivory-400/20 mx-0.5">·</span>
              )}
            </motion.div>
          );
        })}
      </div>
    );
  }

  // 垂直模式（桌面左栏）
  return (
    <div className="flex flex-col py-4">
      <div className="px-4 mb-3">
        <h3 className="font-serif text-gold-400 text-lg leading-none">流程</h3>
        <p className="text-[10px] text-ivory-400/50 tracking-[0.25em] mt-1">
          WORKFLOW
        </p>
      </div>
      <div className="relative px-4">
        {nodes.map((node, i) => {
          const isActive = node.status === "active";
          const isDone = node.status === "done";
          const isCancelled = node.status === "cancelled";
          return (
            <motion.div
              key={node.label + i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.08 }}
              className="relative flex items-start gap-3 pb-6 last:pb-0"
            >
              {i < nodes.length - 1 && (
                <div
                  className={`absolute left-[11px] top-6 bottom-0 w-px ${
                    isDone ? "bg-gold-500/50" : "bg-brown-700/60"
                  }`}
                />
              )}
              <div
                className={`relative z-10 w-6 h-6 rounded-full flex items-center justify-center border transition-all ${
                  isDone
                    ? "bg-gold-500 border-gold-500 text-charcoal-900"
                    : isActive
                    ? "bg-charcoal-900 border-gold-500 text-gold-400 shadow-gold-glow"
                    : isCancelled
                    ? "bg-charcoal-900 border-red-500/60 text-red-400"
                    : "bg-charcoal-900 border-brown-700 text-ivory-400/40"
                }`}
              >
                {isDone ? (
                  <Check className="w-3 h-3" />
                ) : isCancelled ? (
                  <X className="w-3 h-3" />
                ) : isActive ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-gold-400 animate-pulse" />
                ) : (
                  <span className="w-1 h-1 rounded-full bg-ivory-400/30" />
                )}
              </div>
              <div className="pt-0.5">
                <div
                  className={`text-sm ${
                    isActive
                      ? "text-gold-300 font-medium"
                      : isDone
                      ? "text-ivory-400"
                      : isCancelled
                      ? "text-red-400/80 line-through"
                      : "text-ivory-400/40"
                  }`}
                >
                  {node.label}
                </div>
                {isActive && (
                  <div className="text-[10px] text-gold-500/70 mt-0.5 tracking-wider">
                    进行中
                  </div>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
