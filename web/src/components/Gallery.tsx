import { motion } from "framer-motion";
import {
  Check,
  RefreshCw,
  Pencil,
  Image as ImageIcon,
  FileText,
  Video,
} from "lucide-react";
import type { Artifact } from "@/types";

interface Props {
  artifacts: Artifact[];
  accepted: boolean;
  onAccept: () => void;
  onModify: () => void;
  onRedo: () => void;
}

/** 取 artifact_id 短码用于展示 */
function shortId(id: string): string {
  return id.length > 8 ? id.slice(-8) : id;
}

function ArtifactTile({
  artifact,
  index,
}: {
  artifact: Artifact;
  index: number;
}) {
  const Icon =
    artifact.kind === "IMAGE"
      ? ImageIcon
      : artifact.kind === "VIDEO"
      ? Video
      : FileText;

  const isRealImage = artifact.kind === "IMAGE" && artifact.url_or_path && artifact.url_or_path.startsWith("http");
  const imageType = artifact.metadata?.image_type as string | undefined;

  const typeLabels: Record<string, string> = {
    main: "主图",
    detail: "详情图",
    scene: "场景图",
    poster: "海报",
    carousel: "轮播图",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 * index, type: "spring", stiffness: 200, damping: 20 }}
      whileHover={{ scale: 1.03 }}
      className="group relative aspect-square rounded-xl overflow-hidden border border-gold-500/30 bg-gradient-to-br from-brown-700 via-charcoal-800 to-brown-800"
    >
      {isRealImage ? (
        <img
          src={artifact.url_or_path!}
          alt={`Generated ${typeLabels[imageType || "main"] || "image"} ${index + 1}`}
          className="w-full h-full object-cover"
          loading="lazy"
        />
      ) : (
        <>
          <div
            className="absolute inset-0 opacity-30 group-hover:opacity-50 transition"
            style={{
              background:
                "radial-gradient(circle at 30% 30%, rgba(201,169,97,0.4), transparent 60%)",
            }}
          />
          <div className="relative h-full flex flex-col items-center justify-center gap-2">
            <Icon className="w-7 h-7 text-gold-400" />
            <div className="text-[10px] text-ivory-400/60 font-mono">
              #{shortId(artifact.artifact_id)}
            </div>
            <div className="text-[10px] text-gold-300/80 tracking-wider">
              {artifact.kind}
            </div>
          </div>
        </>
      )}
      {imageType && (
        <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/50 backdrop-blur text-[9px] text-gold-300">
          {typeLabels[imageType] || imageType}
        </div>
      )}
    </motion.div>
  );
}

/**
 * 产出物画廊（右侧，delivered/accepted 时显示）
 * mock://image/xxx 无法直接展示，用渐变占位块 + 琥珀边框 + 图标 + 短码
 */
export default function Gallery({
  artifacts,
  accepted,
  onAccept,
  onModify,
  onRedo,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 40 }}
      transition={{ type: "spring", stiffness: 240, damping: 22 }}
      className="bg-brown-800/70 backdrop-blur border border-gold-500/20 rounded-2xl overflow-hidden shadow-warm-glow"
    >
      <div className="h-1 bg-gradient-to-r from-gold-600 via-gold-400 to-terracotta-500" />
      <div className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-serif text-xl text-gold-300">产出物</h3>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-gold-500/15 text-gold-300 border border-gold-500/30 tracking-wider">
            {artifacts.length} 件
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          {artifacts.map((a, i) => (
            <ArtifactTile key={a.artifact_id} artifact={a} index={i} />
          ))}
        </div>

        {!accepted ? (
          <div className="flex flex-col gap-2">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onAccept}
              className="w-full py-2.5 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition flex items-center justify-center gap-1.5"
            >
              <Check className="w-4 h-4" /> 可以了，验收
            </motion.button>
            <div className="flex gap-2">
              <button
                onClick={onModify}
                className="flex-1 py-2 rounded-full border border-gold-500/40 text-gold-300 hover:bg-gold-500/10 text-xs transition flex items-center justify-center gap-1.5"
              >
                <Pencil className="w-3 h-3" /> 改第 N 张
              </button>
              <button
                onClick={onRedo}
                className="flex-1 py-2 rounded-full border border-terracotta-500/40 text-terracotta-300 hover:bg-terracotta-500/10 text-xs transition flex items-center justify-center gap-1.5"
              >
                <RefreshCw className="w-3 h-3" /> 重做
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-3 rounded-full bg-gold-500/10 border border-gold-500/30 text-gold-300 text-sm">
            ✓ 已验收归档
          </div>
        )}
      </div>
    </motion.div>
  );
}
