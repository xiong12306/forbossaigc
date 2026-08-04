# 手机端适配 Implementation Plan

> **For agentic workers:** 前端响应式适配。本项目是 git 仓库但**除非用户要求否则不 commit**，"Commit" 步骤替换为"跑 `cd web && npm run build` 确保通过"。结构性改动（Task 1-3）有精确代码；内页（Task 4）按机械三规则扫。视觉验证（375px 无横向溢出）由主流程用 preview 工具在 verify 阶段做。Steps use checkbox。

**Goal:** 让「AI 助手」(Home) 与「电商平台」(PlatformLayout + 8 内页) 在手机端可正常导航与使用；桌面端零回归。

**Architecture:** 断点统一 `lg`(1024)。BrandBar 切换器移动端可见；PlatformLayout 侧栏 `< lg` 改左滑抽屉 + 移动顶栏（汉堡）；Home 收尾堆叠；8 内页按"外边距响应式 + 网格塌列 + 宽表格横滚"三规则处理。纯 Tailwind 类 + 一个抽屉 `useState`，不加依赖。

**Tech Stack:** React 18 + TypeScript + Tailwind + react-router-dom + lucide-react + framer-motion。参考 spec：`docs/superpowers/specs/2026-07-27-mobile-responsive-design.md`。

## Global Constraints

- 断点分界 `lg`（`< lg` 移动，`lg+` 桌面保持现状，桌面零回归）。
- 不加新依赖；不改后端；不改桌面端已有布局类的桌面表现。
- 汉堡图标用 lucide `Menu` / `X`（已装 lucide-react）。
- 验证命令：`cd web && npm run build`（含 `tsc -b`，类型 + 构建）。
- 视觉验收：375px 视口下 `document.documentElement.scrollWidth <= window.innerWidth`（无横向溢出）。

---

### Task 1: BrandBar 切换器移动端可见

**Files:** Modify `web/src/components/BrandBar.tsx`

- [ ] **Step 1: 改导航切换 `<nav>`** — 把 `className="hidden sm:flex items-center gap-1 ml-2"` 改为移动端也显示、更紧凑：

```tsx
<nav className="flex items-center gap-1 sm:ml-2">
```

并把两个 `<a>` 的文字在超窄屏可留（pill 已足够小）；如需更紧凑可给文字包 `hidden xs:inline`，但默认保留文字。品牌副标题 `老板 AI 助手` 那行加 `hidden sm:block` 避免窄屏挤：找到 `<div className="text-[11px] text-ivory-400/70 mt-1 tracking-[0.2em]">老板 AI 助手</div>`，改成 `className="hidden sm:block text-[11px] ..."`。

- [ ] **Step 2: 构建校验** — `cd web && npm run build`，预期通过。

---

### Task 2: PlatformLayout 侧栏 → 移动抽屉 + 顶栏

**Files:** Modify `web/src/components/PlatformLayout.tsx`

**Interfaces:** 新增本地状态 `open`；抽屉在 `< lg` 用 fixed + translate；`lg+` 恢复 static 侧栏。

- [ ] **Step 1: 顶部加 import 与状态** — 在 import 区把 lucide 增补 `Menu, X`；组件内加状态与路由联动：

```tsx
import { useState, useEffect } from "react";
// lucide-react 增补：Menu, X
```
在 `const username = getUser();` 下方加：
```tsx
  const [open, setOpen] = useState(false);
  useEffect(() => { setOpen(false); }, [location.pathname]);
```

- [ ] **Step 2: 外层容器 + 移动顶栏 + 遮罩** — 把最外层 `return (<div className="h-screen w-screen flex ...">` 结构调整为：外层 `relative`，`< lg` 顶部一条移动栏，`aside` 变可滑出，`main` 补顶部留白。

将最外层 `<div>` 起始与侧栏 `<aside>` 前，替换为：

```tsx
  return (
    <div className="h-screen w-screen flex bg-charcoal-900 text-ivory-500 overflow-hidden">
      {/* 移动顶栏（lg 以下） */}
      <div className="lg:hidden fixed top-0 inset-x-0 z-30 h-14 flex items-center gap-3 px-4 bg-brown-900/90 backdrop-blur border-b border-gold-500/15">
        <button
          onClick={() => setOpen(true)}
          aria-label="打开菜单"
          className="p-2 -ml-2 rounded-lg text-ivory-400/80 hover:text-gold-300 hover:bg-brown-800/50 transition"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-gold-500 to-terracotta-500 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-charcoal-900" />
          </div>
          <span className="font-serif text-gold-400">BossAIGC</span>
        </div>
      </div>

      {/* 遮罩（抽屉打开时，lg 以下） */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="lg:hidden fixed inset-0 z-40 bg-charcoal-900/60 backdrop-blur-sm"
        />
      )}

      {/* 侧边栏 / 抽屉 */}
      <aside
        className={`w-[220px] flex-shrink-0 flex flex-col bg-brown-900/60 border-r border-gold-500/15
          fixed inset-y-0 left-0 z-50 transform transition-transform duration-300
          ${open ? "translate-x-0" : "-translate-x-full"}
          lg:static lg:translate-x-0 lg:z-auto`}
      >
```

- [ ] **Step 3: 抽屉内加关闭按钮（仅 lg 以下）** — 在侧栏 Logo 块 `<div className="px-5 py-4 border-b border-brown-700/50">` 内的 `flex items-center gap-2.5` 之后（Logo 右侧）加一个关闭按钮，仅移动端显示。把该 Logo 容器改为两端对齐并加按钮：

```tsx
        <div className="px-5 py-4 border-b border-brown-700/50 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {/* …原有 Logo 图标 + 文案不变… */}
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="关闭菜单"
            className="lg:hidden p-1.5 rounded-lg text-ivory-400/70 hover:text-gold-300 hover:bg-brown-800/50 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
```

- [ ] **Step 4: 内容区补移动顶栏留白** — 把内容区 `<main className="flex-1 overflow-y-auto">` 改为：

```tsx
      <main className="flex-1 overflow-y-auto pt-14 lg:pt-0">
```

- [ ] **Step 5: 构建校验** — `cd web && npm run build`，预期通过。

---

### Task 3: Home（AI 助手）响应式收尾

**Files:** Modify `web/src/pages/Home.tsx`（仅在发现横向溢出/不可用时微调）

- [ ] **Step 1: 核对无横向溢出** — Home 已 `flex-col lg:flex-row` 堆叠、右面板 `max-h-[40vh]`、底部水平时间线。检查：最外层已 `overflow-hidden`；确认 `ChatStream` 内图片/画廊无固定宽导致溢出。若 `SidePanel`/`Gallery` 里有 `w-[...]` 固定宽或图片缺 `max-w-full`，加 `max-w-full`。Task 1 已让切换器移动端可见，Home 顶部切换即可用。

- [ ] **Step 2: 构建校验** — `cd web && npm run build`，预期通过。

（注：Home 结构性响应式已基本就绪，本任务多为核对 + 必要微调，不重排。）

---

### Task 4: 平台 8 内页机械三规则扫

**Files:** Modify `web/src/pages/{Dashboard,ImageStudio,Copywriting,Products,Assets,Marketing,Service,Finance}.tsx`

对每个页面依次读文件并应用三规则（逐页 build 校验）：

- [ ] **规则 A — 外边距响应式**：页面根容器若为 `p-6`/`p-8`/`px-8` 等固定大内边距，改为 `p-4 lg:p-8`（或 `px-4 lg:px-8` 等比）。
- [ ] **规则 B — 顶层网格塌列**：
  - `grid-cols-4` → `grid-cols-2 lg:grid-cols-4`
  - `grid-cols-3` → `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`
  - `grid-cols-2`（顶层统计/卡片）→ `grid-cols-1 sm:grid-cols-2`
  - 已带响应式前缀的（如 `lg:grid-cols-2`）保持不动。
- [ ] **规则 C — 宽表格/宽图表横滚**：对固定多列行（如 Products 的 `grid-cols-12` 行组、Dashboard 图表容器），用一层 `<div className="overflow-x-auto -mx-4 px-4 lg:mx-0 lg:px-0">` 包住，并给表体最外层加 `min-w-[720px] lg:min-w-0`（列多则取更大值如 900），使窄屏横向滚动、桌面恢复自适应。

**逐页步骤（每页重复）：**
- [ ] **Step 1**：Read 该页，定位根容器 padding、顶层 grid、宽表格/图表。
- [ ] **Step 2**：按规则 A/B/C 编辑（只加/改响应式类，不动数据逻辑与桌面表现）。
- [ ] **Step 3**：`cd web && npm run build` 通过后进入下一页。

完成 8 页后：
- [ ] **Step 4: 全量构建** — `cd web && npm run build`，预期通过。

---

### Task 5: 移动端视觉验证（verify，由主流程用 preview 执行）

- [ ] **Step 1**：确保 vite 开发服务器在 5173 运行（已在跑；否则 `cd web && npm run dev`）。
- [ ] **Step 2**：preview 切 375×812 移动视口，逐屏验证：
  1. `/`（登录后）Home：切换器可见 → 点「电商平台」进入 `/platform`。
  2. `/platform`：点汉堡开抽屉、点遮罩关、点各导航项跳转并自动收起、点「AI 语音助手」切回 `/`。
  3. 逐个访问 8 内页：`eval` 检查 `document.documentElement.scrollWidth <= window.innerWidth`（无横向溢出），关键按钮/文字可点可读。
- [ ] **Step 3**：切回桌面视口（1280）抽查 Home/Platform 与改动前一致（无回归）。
- [ ] **Step 4**：发现溢出/破版的页面回到 Task 4 规则修正，重验。

---

## Self-Review

- **Spec 覆盖**：§3 切换器→Task1+Task2(顶栏/抽屉含 AI语音助手链接原样保留)；§4 抽屉→Task2；§5 Home→Task3；§6 三规则→Task4；§7 验证→Task5；§8 YAGNI（不重排/不加依赖/不改后端）遵守。
- **占位符**：结构性 Task1-3 给出精确类名与代码；Task4 为规则化扫（前端响应式扫的固有形态），以逐页 build + 375px 无溢出为客观验收，不含模糊的"看情况处理"。
- **一致性**：断点统一 `lg`；抽屉 `open` 状态 + `location` 联动关闭；桌面 `lg:static lg:translate-x-0` 恢复原状。
- **注意点**：Task2 修改 `<aside>` 时保留其内所有现有子节点（Logo/nav/底部区）不变，仅改外层 className 与 Logo 容器布局 + 加关闭按钮；`main` 加 `pt-14 lg:pt-0` 让内容不被移动顶栏遮挡。
