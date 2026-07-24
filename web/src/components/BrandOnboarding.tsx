import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";

const STORAGE_KEY = "bossaigc.onboarded.v1";

/**
 * 首次进入的品牌风格引导浮层
 * 用 localStorage 记住已看过
 */
export default function BrandOnboarding() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
  }, []);

  const close = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-charcoal-900/80 backdrop-blur-sm px-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={close}
        >
          <motion.div
            onClick={(e) => e.stopPropagation()}
            initial={{ scale: 0.92, opacity: 0, y: 10 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ type: "spring", stiffness: 260, damping: 22 }}
            className="relative max-w-md w-full bg-brown-800 border border-gold-500/30 rounded-2xl overflow-hidden shadow-warm-glow"
          >
            <div className="h-1 bg-gradient-to-r from-gold-600 via-gold-400 to-terracotta-500" />
            <div className="p-8 text-center">
              <motion.div
                initial={{ rotate: -10, scale: 0 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
                className="w-14 h-14 rounded-full bg-gradient-to-br from-gold-500 to-terracotta-500 mx-auto mb-4 flex items-center justify-center shadow-gold-glow"
              >
                <Sparkles className="w-6 h-6 text-charcoal-900" />
              </motion.div>
              <h2 className="font-serif text-3xl text-gold-300 mb-2">欢迎，老板</h2>
              <p className="text-sm text-ivory-400/70 leading-relaxed mb-6">
                BossAIGC 已默认设定品牌风格：
                <br />
                <span className="text-gold-300">轻奢 · 暖色调 · 大面积留白</span>
                <br />
                所有产出将遵循此风格。
              </p>
              <button
                onClick={close}
                className="w-full py-3 rounded-full bg-gold-500 hover:bg-gold-400 text-charcoal-900 font-medium text-sm shadow-gold-glow transition"
              >
                开始使用
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
