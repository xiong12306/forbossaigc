import { RotateCcw, Sparkles, Wand2 } from "lucide-react";

interface Props {
  onReset: () => void;
}

/**
 * 顶部品牌栏：左侧 Logo + 导航切换 + 右侧风格徽章与重置按钮
 */
export default function BrandBar({ onReset }: Props) {
  return (
    <header className="flex items-center justify-between px-4 sm:px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Sparkles className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="leading-none">
            <div className="font-serif text-xl text-gold-400 tracking-wide">
              BossAIGC
            </div>
            <div className="text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">
              老板 AI 助手
            </div>
          </div>
        </div>

        {/* 导航切换 */}
        <nav className="hidden sm:flex items-center gap-1 ml-2">
          <a
            href="/"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-gold-300 bg-gold-500/10 border border-gold-500/30 transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI 助手
          </a>
          <a
            href="/platform"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/60 transition border border-transparent hover:border-gold-500/30"
          >
            <Wand2 className="w-3.5 h-3.5" />
            电商平台
          </a>
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-gold-500/40 text-xs text-gold-300 bg-brown-800/50">
          <span className="w-1.5 h-1.5 rounded-full bg-terracotta-500" />
          轻奢 · 暖色调
        </span>
        <button
          onClick={onReset}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-ivory-400/80 hover:text-gold-300 hover:bg-brown-800/60 transition border border-transparent hover:border-gold-500/30"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">重置会话</span>
        </button>
      </div>
    </header>
  );
}
