import { RotateCcw, Sparkles, Wand2, ImageIcon, Layout, Menu } from "lucide-react";
import { useLocation, Link } from "react-router-dom";

interface Props {
  onReset: () => void;
  onOpenGallery?: () => void;
  onToggleSidebar?: () => void;
}

/**
 * 顶部品牌栏：左侧 Logo + 导航切换 + 右侧风格徽章与重置按钮
 */
export default function BrandBar({ onReset, onOpenGallery, onToggleSidebar }: Props) {
  const location = useLocation();
  const isHome = location.pathname === "/";
  const isCanvas = location.pathname === "/canvas";
  const isPlatform = location.pathname.startsWith("/platform");

  return (
    <header className="flex items-center justify-between px-4 sm:px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20 relative z-50">
      <div className="flex items-center gap-3 sm:gap-4">
        {/* 移动端菜单按钮 */}
        {onToggleSidebar && isHome && (
          <button
            onClick={onToggleSidebar}
            className="lg:hidden inline-flex items-center justify-center w-9 h-9 rounded-lg text-ivory-400/80 hover:text-gold-300 hover:bg-brown-800/60 transition"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
            <Sparkles className="w-4 h-4 text-charcoal-900" />
          </div>
          <div className="leading-none">
            <div className="font-serif text-xl text-gold-400 tracking-wide">
              BossAIGC
            </div>
            <div className="hidden sm:block text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">
              老板 AI 助手
            </div>
          </div>
        </div>

        {/* 导航切换 */}
        <nav className="hidden sm:flex items-center gap-1 sm:ml-2">
          <Link
            to="/"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition border ${
              isHome
                ? "text-gold-300 bg-gold-500/10 border-gold-500/30"
                : "text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/60 border-transparent hover:border-gold-500/30"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI 助手
          </Link>
          <Link
            to="/canvas"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition border ${
              isCanvas
                ? "text-gold-300 bg-gold-500/10 border-gold-500/30"
                : "text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/60 border-transparent hover:border-gold-500/30"
            }`}
          >
            <Layout className="w-3.5 h-3.5" />
            无限画布
          </Link>
          <Link
            to="/platform"
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition border ${
              isPlatform
                ? "text-gold-300 bg-gold-500/10 border-gold-500/30"
                : "text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/60 border-transparent hover:border-gold-500/30"
            }`}
          >
            <Wand2 className="w-3.5 h-3.5" />
            电商平台
          </Link>
        </nav>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {onOpenGallery && (
          <button
            onClick={onOpenGallery}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-ivory-400/80 hover:text-gold-300 hover:bg-brown-800/60 transition border border-transparent hover:border-gold-500/30"
          >
            <ImageIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">图库</span>
          </button>
        )}
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
