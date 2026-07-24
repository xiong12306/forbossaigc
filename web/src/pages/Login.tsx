import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Lock, User, Sparkles, Shield } from "lucide-react";
import { login, isLoggedIn } from "@/lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("boss");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isLoggedIn()) {
      navigate("/platform", { replace: true });
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError("请输入用户名和密码");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate("/platform", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-charcoal-900 flex items-center justify-center px-4">
      {/* 背景装饰 */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-gold-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-terracotta-500/5 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-gold-500 to-terracotta-500 mb-4 shadow-gold-glow">
            <Sparkles className="w-8 h-8 text-charcoal-900" />
          </div>
          <h1 className="font-serif text-3xl text-gold-400 tracking-wider">BossAIGC</h1>
          <p className="text-ivory-400/50 text-sm mt-2">电商老板AI助手</p>
        </div>

        {/* 登录卡片 */}
        <div className="bg-brown-900/50 backdrop-blur-xl border border-gold-500/20 rounded-2xl p-8 shadow-2xl">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-5 h-5 text-gold-400" />
            <span className="text-gold-300 font-medium">老板登录</span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 用户名 */}
            <div>
              <label className="text-sm text-ivory-400/70 mb-2 block">用户名</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ivory-400/40" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-charcoal-900/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/30 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition"
                  autoFocus
                />
              </div>
            </div>

            {/* 密码 */}
            <div>
              <label className="text-sm text-ivory-400/70 mb-2 block">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ivory-400/40" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-charcoal-900/60 border border-gold-500/20 text-ivory-500 placeholder-ivory-400/30 focus:outline-none focus:border-gold-500/60 focus:ring-1 focus:ring-gold-500/30 transition"
                  onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(e); }}
                />
              </div>
            </div>

            {/* 错误提示 */}
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
              >
                {error}
              </motion.div>
            )}

            {/* 登录按钮 */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-gold-500 to-terracotta-500 text-charcoal-900 font-medium hover:shadow-gold-glow transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-charcoal-900/30 border-t-charcoal-900 rounded-full animate-spin" />
                  登录中...
                </>
              ) : (
                "登 录"
              )}
            </button>
          </form>

          {/* 默认密码提示 */}
          <div className="mt-5 pt-5 border-t border-gold-500/10">
            <p className="text-xs text-ivory-400/40 text-center">
              默认账号：boss / boss123
            </p>
          </div>
        </div>

        {/* 底部 */}
        <p className="text-center text-ivory-400/30 text-xs mt-6">
          BossAIGC v0.3.0 · 一人电商智能助手
        </p>
      </motion.div>
    </div>
  );
}
