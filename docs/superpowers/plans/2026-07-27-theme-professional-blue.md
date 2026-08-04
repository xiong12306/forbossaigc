# 全局换肤：专业蓝（亮色）Implementation Plan

> **For agentic workers:** 纯主题换色。git 仓库但**不 commit**（用户未要求）。无单元测试（纯视觉）；每任务校验 = `cd web && npm run build` 通过。桌面+375px 的对比度视觉验证（Task 5）由主流程用 preview 做。Steps use checkbox。

**Goal:** 把前端从"暗·轻奢金"整体换成"亮·专业蓝"，只改主题变量层 + 少量硬编码图表 hex。

**Architecture:** 保留 5 个 token 色板类名（charcoal/brown/gold/terracotta/ivory），重定义其 hex（暗→亮翻转，对比自动保住）；渐变/光晕用 token 自动变蓝；index.css 换浅底；Dashboard/Finance 写死的金/陶土图表 hex 按映射表换蓝/天蓝。970 处组件类、布局、后端均不动。

**Tech Stack:** Tailwind v3.4 + Vite + React。参考 spec：`docs/superpowers/specs/2026-07-27-theme-professional-blue-design.md`。

## Global Constraints

- 只改本计划列出的文件；不改组件 token 类、不动布局/响应式、不动后端、不改 AIGC "轻奢暖色调"图片风格文案。
- 校验：`cd web && npm run build`（含 tsc）通过。
- 不 commit。

---

### Task 1: tailwind.config.js 重定义色板 + 阴影

**Files:** Modify `web/tailwind.config.js`

- [ ] **Step 1: 替换 `theme.extend.colors` 五个色板为新值**（保留键名）：

```js
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
          400: "#475569",
          500: "#1E293B",
        },
      },
```

- [ ] **Step 2: 替换 `boxShadow`**：

```js
      boxShadow: {
        "gold-glow": "0 0 20px rgba(37, 99, 235, 0.22)",
        "warm-glow":
          "0 8px 24px rgba(15, 23, 42, 0.08), 0 0 1px rgba(37, 99, 235, 0.15)",
      },
```

- [ ] **Step 3: 校验** `cd web && npm run build`，预期通过。

---

### Task 2: index.css 换浅底 + 变量 + 滚动条

**Files:** Modify `web/src/index.css`

- [ ] **Step 1: 替换 `:root` 的 8 个颜色变量**：

```css
  --color-charcoal: #f4f7fb;
  --color-charcoal-800: #e9eef5;
  --color-brown: #e2e8f0;
  --color-brown-700: #e2e8f0;
  --color-brown-800: #f1f5f9;
  --color-gold: #2563eb;
  --color-terracotta: #0ea5e9;
  --color-ivory: #1e293b;
```
（若 `:root` 里缺 `--color-brown-700` 就照现有键补齐，键名与现文件保持一致。）

- [ ] **Step 2: 替换 `body` 背景**（去暗底/暖径向渐变/SVG 噪点，改干净浅底 + 极淡蓝顶光）：

```css
body {
  background-color: #f4f7fb;
  color: #1e293b;
  background-image: radial-gradient(
    ellipse at top,
    rgba(37, 99, 235, 0.04),
    transparent 55%
  );
  background-attachment: fixed;
}
```

- [ ] **Step 3: 滚动条 thumb 换浅蓝灰** —— 找到 `::-webkit-scrollbar-thumb` 规则，把其金色 `background` 改为：

```css
  background: #cbd5e1;
```
并把其 `:hover`（若有）改为 `#94a3b8`。

- [ ] **Step 4: 校验** `cd web && npm run build`，预期通过。

---

### Task 3: 硬编码图表 hex 映射替换

**Files:** Modify `web/src/pages/Dashboard.tsx`、`web/src/pages/Finance.tsx`（如其它页也命中同名 hex 一并改）

- [ ] **Step 1: 全量定位残留旧 hex**
Run: `cd web/src && grep -rnE "#(B89650|D4B970|E0C988|C9A961|C26548|D97757|E08A6E|1A1715|221E1B|3D3530|332C28|2A2421|1F1A17|C9A961|F5EFE6|E8DFD0|131110)" pages components`
记录所有命中行（预期主要在 Dashboard.tsx / Finance.tsx 的图表渐变与色点）。

- [ ] **Step 2: 按映射表逐一替换**（大小写不敏感，保留渐变方向/停靠点/其余语法不变）：

| 旧（金/陶土/暖） | 新（蓝/天蓝） |
|---|---|
| `#B89650` | `#1D4ED8` |
| `#D4B970` | `#3B82F6` |
| `#E0C988` | `#60A5FA` |
| `#C9A961` | `#2563EB` |
| `#C26548` | `#0284C7` |
| `#D97757` | `#0EA5E9` |
| `#E08A6E` | `#38BDF8` |

已知命中（供核对，实际以 grep 为准）：
- `Dashboard.tsx`：`linear-gradient(to top, #B89650 0%, #D4B970 50%, #E0C988 100%)` → `... #1D4ED8 0%, #3B82F6 50%, #60A5FA 100%`
- `Finance.tsx`：`to right, #B89650 0%, #D4B970 50%, #E0C988 100%`、`to top, #B89650 0%, #D4B970 60%, #E0C988 100%` → 蓝系；`to top, #C26548 0%, #D97757 60%, #E08A6E 100%`、`to right, #C26548, #D97757` → 天蓝系；单点 `#D4B970`→`#3B82F6`、`#D97757`→`#38BDF8`。

- [ ] **Step 3: 复核无残留** —— 重跑 Step 1 的 grep，预期无输出（除 `assets/react.svg` 里 `#00D8FF` 等无关第三方图标，可忽略）。

- [ ] **Step 4: 校验** `cd web && npm run build`，预期通过。

---

### Task 4: 全量构建

- [ ] **Step 1:** `cd web && npm run build` —— 预期 tsc + vite 均通过（仅既有 chunk-size 提醒可忽略）。

---

### Task 5: 视觉对比度验证（verify，主流程用 preview）

- [ ] **Step 1:** 确保 vite 在 5173（preview 托管）。
- [ ] **Step 2:** 桌面(1280) + 手机(375) 各跑一遍，逐屏：登录页、AI 助手(Home)、平台 8 内页。每屏：
  - 截图看整体观感（是否浅底白卡蓝强调、无残留暗底/金）。
  - `eval`/`inspect` 取关键文字元素与其背景的计算色，核对对比度（正文文字非浅色、按钮文字在蓝底可读）。
  - **重点排查 `text-charcoal-*`**：`grep` 出所有 `text-charcoal` 用法，逐处确认其所在元素背景是深/蓝底（浅字可读）而非浅底（会隐形）；命中浅底隐形的改为 `text-ivory-*`。
- [ ] **Step 3:** 发现低对比/隐形处 → 针对性修（改该处类）→ 复验该屏。
- [ ] **Step 4:** 抽查响应式无回归（抽屉/切换器/无横向溢出，沿用上一轮验证手法）。

---

## Self-Review

- **Spec 覆盖**：§3 色板→Task1；index.css→Task2；图表 hex→Task3；构建→Task4；§5 风险(对比度/text-charcoal)→Task5。全覆盖。
- **占位符**：Task1/2 给出完整代码；Task3 给出精确映射表 + grep 命令兜底残留；无模糊步骤。
- **一致性**：token 键名与现 config 一致（charcoal/brown/gold/terracotta/ivory 的现有 stop：charcoal 800/900、brown 700/800/900、gold 300-600、terracotta DEFAULT/400/500/600、ivory DEFAULT/400/500），新值一一对应，无新增/缺失 stop。
- **注意点**：Task5 的 `text-charcoal-*` 排查是本次唯一高风险点（原深字变浅，浅底上会隐形），必须逐处核对；这是"改主题变量层"策略的固有代价，用 preview 兜住。
