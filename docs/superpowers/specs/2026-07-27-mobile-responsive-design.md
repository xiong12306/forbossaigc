# AI 助手 + 电商平台 手机端适配 — 设计方案

- 日期：2026-07-27
- 状态：已评审通过，待写实现计划
- 范围：让「AI 助手」(Home) 与「电商平台」(PlatformLayout + 8 内页) 在手机端可正常导航与使用（"能用"优先，非逐页像素级精修）

## 1. 背景与目标

现状（`web/src`）：
- **切换器不可用**：`BrandBar` 里的「AI 助手 / 电商平台」切换 pill 带 `hidden sm:flex`，手机上被隐藏；且切换器只在 Home 页有。
- **平台不适配**：`PlatformLayout` 用固定 `w-[220px]` 侧栏，手机上挤占内容、无汉堡/抽屉，且从平台切回助手的入口埋在侧栏里。
- **内页破版风险**：如 `Products` 用 `grid-cols-12` 固定表格行、`Dashboard` 用多列统计网格，窄屏会横向溢出。
- Home 已有部分响应式（时间线 `md` 折叠、右面板 `lg` 堆叠），但切换器隐藏、细节需收尾。

目标：手机端两个板块都能**正常导航与使用**——切换器可见、平台侧栏改抽屉、所有页面无横向溢出、表格/图表在窄屏可滚动或塌列、文字可读。桌面端零回归。

## 2. 断点约定

统一以 Tailwind `lg`（1024px）为桌面/移动分界（与 Home 现有 `lg:flex-row` 一致）：`< lg` 移动布局，`lg+` 保持现状。局部卡片网格可用 `sm`(640)/`md`(768) 做中间档塌列。

## 3. 跨板块切换

- `BrandBar` 切换器：移除 `hidden sm:flex` 的隐藏，改为移动端也显示（紧凑 pill，可图标为主 + 文字）。使 Home 手机端能进入 `/platform`。
- `PlatformLayout` 移动端新增顶部小栏（Logo + 汉堡按钮）；抽屉内保留现有「AI 语音助手」链接（→ `/`）用于切回助手。
- 结果：手机端两个方向均可切换。

## 4. PlatformLayout 响应式（侧栏 → 抽屉）

- `< lg`：
  - 侧栏改为**左侧滑出抽屉**：`fixed inset-y-0 left-0 z-50` + `transform`/`-translate-x-full`↔`translate-x-0` 过渡；抽屉打开时渲染半透明背景遮罩（`fixed inset-0 z-40`，点击关闭）。
  - 新增移动顶栏（`lg:hidden`）：左汉堡按钮（`Menu` 图标）+ 居中/左对齐 Logo。
  - 抽屉内容复用现有 `NAV_GROUPS` 渲染与底部区（AI 语音助手 / 设置 / 退出）。
  - 状态：`const [open, setOpen] = useState(false)`；`useEffect` 监听 `location.pathname` 变化时 `setOpen(false)`（点菜单跳转后自动收起）。
- `lg+`：现有 220px 固定侧栏与内容区**不改**（`lg:static lg:translate-x-0 lg:z-auto`，遮罩 `lg:hidden`）。
- 内容区 `main` 在移动端顶部留出移动顶栏高度。

## 5. Home（AI 助手）响应式收尾

- 确保 `BrandBar` 切换器移动端可见（见 §3）。
- 保持现有堆叠（聊天流主区 + 底部 `max-h-40vh` 摘要/画廊面板 + 底部水平时间线）；核对无横向溢出、输入框可达、画廊图片 `max-w-full`。
- 仅做必要微调，不重排。

## 6. 平台 8 内页（能用级，机械三规则）

对 `Dashboard/ImageStudio/Copywriting/Products/Assets/Marketing/Service/Finance` 逐页按以下规则处理，避免破版而非重设计：

1. **外边距响应式**：页面容器 `p-6`/`p-8` 等 → `p-4 lg:p-8`（或等比）。
2. **顶层卡片/统计网格塌列**：`grid-cols-4`→`grid-cols-2 lg:grid-cols-4`；`grid-cols-2`→`grid-cols-1 sm:grid-cols-2`；`lg:grid-cols-2` 保持。
3. **宽表格/宽图表**：外层包 `overflow-x-auto` 容器，表体给 `min-w-[720px]`（按实际列数取值），窄屏横向滚动不破版；不做卡片化重排。

## 7. 验证（verify 阶段）

- 用 preview 工具在 **375px 移动视口**逐屏验证：
  1. Home：切换器可见、点击进入 `/platform`。
  2. Platform：汉堡打开抽屉、遮罩关闭、点导航项跳转并自动收起、「AI 语音助手」切回 Home。
  3. 8 内页逐个：`document.documentElement.scrollWidth ≤ window.innerWidth`（无横向溢出）；关键文字/按钮可读可点。
- `lg+` 桌面视口抽查 Home/Platform 布局与改动前一致（无回归）。
- 跑 `cd web && npm run build`（含 `tsc -b`）确保类型检查与构建通过。

## 8. 明确不做（YAGNI）

- 不做 8 页逐页卡片化 / 像素级手机专属设计（属"精致"档，本次不含）。
- 不改后端、不改桌面端布局、不新增依赖（仅 Tailwind 响应式类 + 一个抽屉 `useState`）。
- 不做底部 Tab 栏、不做手势滑动、不做 PWA。

## 9. 验收标准

1. iPhone 尺寸（375px）下，能在「AI 助手」与「电商平台」之间来回切换。
2. 电商平台手机端：汉堡抽屉可开合、8 个导航项可跳转、可切回助手。
3. 全部页面（Home + 8 内页）在 375px 下无横向溢出，内容可读、可操作（表格窄屏横向滚动可接受）。
4. 桌面端（`lg+`）布局与改动前一致。
5. `npm run build` 通过。
