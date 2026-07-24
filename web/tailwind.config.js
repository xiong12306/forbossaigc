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
        // 主背景：深炭灰
        charcoal: {
          DEFAULT: "#1A1715",
          800: "#221E1B",
          900: "#131110",
        },
        // 卡片底：深褐
        brown: {
          DEFAULT: "#3D3530",
          700: "#332C28",
          800: "#2A2421",
          900: "#1F1A17",
        },
        // 强调：琥珀金
        gold: {
          300: "#E0C988",
          400: "#D4B970",
          500: "#C9A961",
          600: "#B89650",
        },
        // 次强调：赤陶橙
        terracotta: {
          DEFAULT: "#D97757",
          400: "#E08A6E",
          500: "#D97757",
          600: "#C26548",
        },
        // 文字：暖象牙
        ivory: {
          DEFAULT: "#F5EFE6",
          400: "#E8DFD0",
          500: "#F5EFE6",
        },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', "Georgia", "serif"],
        sans: ['"Noto Sans SC"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        // 琥珀金光晕
        "gold-glow": "0 0 20px rgba(201, 169, 97, 0.35)",
        // 卡片柔光阴影
        "warm-glow":
          "0 8px 32px rgba(0, 0, 0, 0.45), 0 0 1px rgba(201, 169, 97, 0.25)",
      },
    },
  },
  plugins: [],
};
