import { AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";
import SummaryCard from "./SummaryCard";
import Gallery from "./Gallery";
import type { ChatStatus, Summary, Artifact } from "@/types";
import type { SelectedTypes } from "./ImageTypeSelector";

interface Props {
  status: ChatStatus | null;
  summary: Summary | null;
  artifacts: Artifact[] | null;
  onConfirm: (selectedTypes?: SelectedTypes) => void;
  onModify: () => void;
  onCancel: () => void;
  onAccept: () => void;
  onRedo: () => void;
  onNewTask: () => void;
}

/**
 * 右侧上下文容器：根据 currentStatus 决定显示 SummaryCard / Gallery / 空态
 * 用 AnimatePresence 切换动画
 */
export default function SidePanel(props: Props) {
  const { status, summary, artifacts } = props;
  const showSummary = status === "awaiting_confirmation" && summary;
  const showGallery =
    (status === "delivered" || status === "accepted") &&
    !!artifacts &&
    artifacts.length > 0;
  const accepted = status === "accepted";

  return (
    <div className="h-full">
      <AnimatePresence mode="wait">
        {showSummary && summary && (
          <SummaryCard
            key="summary"
            summary={summary}
            onConfirm={props.onConfirm}
            onModify={props.onModify}
            onCancel={props.onCancel}
          />
        )}
        {showGallery && artifacts && (
          <Gallery
            key="gallery"
            artifacts={artifacts}
            accepted={accepted}
            onAccept={props.onAccept}
            onModify={props.onModify}
            onRedo={props.onRedo}
            onNewTask={props.onNewTask}
          />
        )}
      </AnimatePresence>

      {!showSummary && !showGallery && (
        <div className="h-full flex flex-col items-center justify-center text-center px-6">
          <Sparkles className="w-8 h-8 text-gold-500/40 mb-3" />
          <div className="text-sm text-ivory-400/50">上下文卡片</div>
          <div className="text-xs text-ivory-400/30 mt-1">
            任务摘要与产出物将在这里呈现
          </div>
        </div>
      )}
    </div>
  );
}
