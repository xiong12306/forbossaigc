import { useState, useEffect } from "react";
import { NavLink, Outlet, useLocation, useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Sparkles,
  Wand2,
  PenLine,
  Package,
  FolderOpen,
  Megaphone,
  Headphones,
  Wallet,
  Settings,
  LogOut,
  Menu,
  X,
  LayoutGrid,
} from "lucide-react";
import { getUser, logout } from "@/lib/auth";

const NAV_GROUPS = [
  {
    title: "总览",
    items: [
      { to: "/platform", label: "数据看板", icon: LayoutDashboard, end: true },
    ],
  },
  {
    title: "AI 创作",
    items: [
      { to: "/platform/image", label: "出图中心", icon: Wand2 },
      { to: "/platform/copywriting", label: "文案生成", icon: PenLine },
      { to: "/platform/assets", label: "素材库", icon: FolderOpen },
    ],
  },
  {
    title: "经营",
    items: [
      { to: "/platform/products", label: "商品管理", icon: Package },
      { to: "/platform/marketing", label: "营销工具", icon: Megaphone },
      { to: "/platform/service", label: "客服中心", icon: Headphones },
      { to: "/platform/finance", label: "财务看板", icon: Wallet },
    ],
  },
];

const TAB_ITEMS = [
  { to: "/", label: "AI 助手", icon: Sparkles },
  { to: "/canvas", label: "无限画布", icon: LayoutGrid },
  { to: "/platform", label: "电商平台", icon: Wand2 },
];

function isTabActive(pathname: string, to: string) {
  if (to === "/") return pathname === "/";
  return pathname.startsWith(to);
}

/**
 * 平台布局：顶部全局Tab栏 + 左侧导航栏 + 右侧内容区
 */
export default function PlatformLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const username = getUser();
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-charcoal-900 text-ivory-500 overflow-hidden">
      {/* 全局顶部 Tab 导航栏（与 BrandBar 保持一致大小） */}
      <header className="flex items-center justify-between px-4 sm:px-6 py-3 bg-brown-900/70 backdrop-blur border-b border-gold-500/20 z-30">
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center shadow-gold-glow">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div className="leading-none">
              <div className="font-serif text-xl text-gold-400 tracking-wide">
                BossAIGC
              </div>
              <div className="hidden sm:block text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">
                老板 AI 助手
              </div>
            </div>
          </Link>

          <nav className="flex items-center gap-1 sm:ml-2">
            {TAB_ITEMS.map((tab) => {
              const Icon = tab.icon;
              const active = isTabActive(location.pathname, tab.to);
              return (
                <Link
                  key={tab.to}
                  to={tab.to}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition border ${
                    active
                      ? "text-gold-300 bg-gold-500/10 border-gold-500/30"
                      : "text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/60 border-transparent hover:border-gold-500/30"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={() => setOpen(true)}
            aria-label="打开菜单"
            className="lg:hidden p-2 -ml-2 rounded-lg text-ivory-400/80 hover:text-gold-300 hover:bg-brown-800/50 transition"
          >
            <Menu className="w-5 h-5" />
          </button>
          <button
            onClick={handleLogout}
            title="退出登录"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs text-ivory-400/60 hover:text-red-400 hover:bg-brown-800/60 transition border border-transparent"
          >
            <LogOut className="w-3.5 h-3.5" />
            退出
          </button>
        </div>
      </header>

      {/* 主体：侧边栏 + 内容 */}
      <div className="flex-1 flex overflow-hidden min-h-0 relative">
        {/* 遮罩（抽屉打开时，lg 以下） */}
        {open && (
          <div
            onClick={() => setOpen(false)}
            className="lg:hidden fixed inset-0 z-40 bg-charcoal-900/60 backdrop-blur-sm"
            style={{ top: 0 }}
          />
        )}

        {/* 侧边栏 / 抽屉 */}
        <aside
          className={`w-[220px] flex-shrink-0 flex flex-col bg-brown-900/60 border-r border-brown-700/50
            fixed lg:static inset-y-0 left-0 z-50 transform transition-transform duration-300
            ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
          style={{ top: 0, paddingTop: "env(safe-area-inset-top)" }}
        >
          {/* 侧边栏头部 */}
          <div className="px-4 py-3 border-b border-brown-700/40 flex items-center justify-between flex-shrink-0">
            <span className="text-xs text-ivory-400/50 tracking-widest font-medium">功能导航</span>
            <button
              onClick={() => setOpen(false)}
              aria-label="关闭菜单"
              className="lg:hidden p-1 rounded text-ivory-400/70 hover:text-gold-500 hover:bg-brown-800/50 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* 导航 */}
          <nav className="flex-1 overflow-y-auto py-3 px-2.5">
            {NAV_GROUPS.map((group) => (
              <div key={group.title} className="mb-4">
                <div className="px-3 mb-1.5 text-[10px] text-ivory-400/40 tracking-widest font-medium">
                  {group.title}
                </div>
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.end}
                      onClick={() => setOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all mb-0.5 ${
                          isActive
                            ? "bg-gold-500/15 text-gold-500 border border-gold-500/25"
                            : "text-ivory-400/70 hover:text-gold-500 hover:bg-brown-800/40 border border-transparent"
                        }`
                      }
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      {item.label}
                    </NavLink>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* 底部 */}
          <div className="px-3 py-3 border-t border-brown-700/50 flex-shrink-0">
            <Link
              to="/"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ivory-400/60 hover:text-gold-500 hover:bg-brown-800/40 transition"
            >
              <Sparkles className="w-4 h-4" />
              AI 语音助手
            </Link>
            <Link
              to="/canvas"
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ivory-400/60 hover:text-gold-500 hover:bg-brown-800/40 transition"
            >
              <LayoutGrid className="w-4 h-4" />
              无限画布
            </Link>
            <div className="flex items-center gap-2.5 px-3 py-2 mt-0.5 rounded-lg text-sm text-ivory-400/40 cursor-default">
              <Settings className="w-4 h-4" />
              设置
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-ivory-400/50 hover:text-red-400 hover:bg-red-500/10 transition mt-0.5 sm:hidden"
            >
              <LogOut className="w-4 h-4" />
              退出登录
            </button>
            {username && (
              <div className="px-3 pt-2 mt-1 border-t border-brown-700/30 text-[10px] text-ivory-400/30 truncate">
                {username}
              </div>
            )}
          </div>
        </aside>

        {/* 内容区 */}
        <main className="flex-1 overflow-y-auto">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="min-h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
    </div>
  );
}
