/** @type {import('tailwindcss').Config} */

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    container: {
      center: true,
    },
    extend: {
      colors: {
        // 注：色板名保留，含义已由"暗·轻奢"改为"亮·专业蓝"——
        // charcoal=浅色页底/面，brown=白卡/浅边框，gold=科技蓝主强调，
        // terracotta=天蓝次强调，ivory=深墨文字。类名沿用，故 970 处用法无需改。
        charcoal: {
          DEFAULT: "#F5F8FC",
          800: "#E9EEF5",
          900: "#F4F7FB",
        },
        brown: {
          DEFAULT: "#E2E8F0",
          700: "#E2E8F0",
          800: "#F1F5F9",
          900: "#FFFFFF",
        },
        gold: {
          300: "#60A5FA",
          400: "#3B82F6",
          500: "#2563EB",
          600: "#1D4ED8",
        },
        terracotta: {
          DEFAULT: "#0EA5E9",
          400: "#38BDF8",
          500: "#0EA5E9",
          600: "#0284C7",
        },
        ivory: {
          DEFAULT: "#0F172A",
          400: "#334155",
          500: "#1E293B",
        },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', "Georgia", "serif"],
        sans: ['"Noto Sans SC"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        "gold-glow": "0 0 20px rgba(37, 99, 235, 0.22)",
        "warm-glow":
          "0 8px 24px rgba(15, 23, 42, 0.08), 0 0 1px rgba(37, 99, 235, 0.15)",
      },
    },
  },
  plugins: [],
};
