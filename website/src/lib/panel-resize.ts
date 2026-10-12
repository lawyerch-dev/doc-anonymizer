/**
 * 面板的「拖拽调宽 + 收起/展开」行为。左栏(导航)与右栏(本页目录)共用这一份 —— 两边的几何
 * 不同, 但状态机一样: 宽度写进一个 CSS 变量, 收起 = 同一个变量取 0 + 一个贴在 `<html>` 上的类。
 *
 * 宽度只认 localStorage 里的值, 不去量元素实际像素 —— 收起之后元素宽度就是 0, 量出来就回不去了。
 */

export interface PanelResizeOptions {
  /** 宽度写进哪个 CSS 变量(样式里取用它决定谁变宽) */
  cssVar: string;
  /**
   * 手柄贴在哪条边。这决定拖动方向的正负:
   * 尾侧(左栏: 手柄在面板右边缘)= 往右拖变宽; 起始侧(右栏: 手柄在目录列左边缘)= 往左拖变宽。
   */
  handle?: "start" | "end";
  /** 拖 1px 改多少宽度。右栏的列宽里含一半留白, 要 2 才跟手 */
  sensitivity?: number;
  min: number;
  max: number;
  fallback: number;
  gripSelector: string;
  toggleSelector: string;
  /** 收起状态贴在 `<html>` 上的类名 */
  collapsedClass: string;
  storageKey: string;
  collapsedStorageKey: string;
}

export function createPanelResizer(options: PanelResizeOptions): void {
  const root = document.documentElement;
  const grip = document.querySelector<HTMLElement>(options.gripSelector);
  const toggle = document.querySelector<HTMLButtonElement>(options.toggleSelector);
  // 指针/方向键位移 → 宽度位移(带正负): RTL 整体镜像, 手柄在起始侧再翻一次
  const ratio =
    (root.dir === "rtl" ? -1 : 1) *
    (options.handle === "start" ? -1 : 1) *
    (options.sensitivity ?? 1);

  let expandedWidth = Number(localStorage.getItem(options.storageKey)) || options.fallback;
  const isCollapsed = () => root.classList.contains(options.collapsedClass);

  function paint() {
    const width = isCollapsed() ? 0 : expandedWidth;
    root.style.setProperty(options.cssVar, `${width}px`);
    grip?.setAttribute("aria-valuenow", String(width));
  }

  function setExpandedWidth(px: number, persist = true) {
    expandedWidth = Math.min(options.max, Math.max(options.min, Math.round(px)));
    if (persist) localStorage.setItem(options.storageKey, String(expandedWidth));
    paint();
  }

  function applyCollapsed(collapsed: boolean, persist = true) {
    root.classList.toggle(options.collapsedClass, collapsed);
    if (persist) localStorage.setItem(options.collapsedStorageKey, collapsed ? "1" : "0");
    toggle?.setAttribute("aria-expanded", String(!collapsed));
    toggle?.setAttribute(
      "aria-label",
      collapsed ? (toggle.dataset.labelExpand ?? "") : (toggle.dataset.labelCollapse ?? ""),
    );
    paint();
  }

  // 首屏对齐: 早脚本只贴了宽度与类名, 按钮的文案 / aria 与手柄数值在这里补齐。
  // 这一趟不落盘 —— 没有面板的页面(比如没有目录的页)不该顺手把用户的偏好改掉。
  applyCollapsed(isCollapsed(), false);

  toggle?.addEventListener("click", () => applyCollapsed(!isCollapsed()));

  if (!grip) return;

  grip.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || isCollapsed()) return;
    // 不用 preventDefault: 它会把焦点一起吞掉, 键盘就没法接着用方向键微调了
    grip.focus({ preventScroll: true });
    const from = expandedWidth;
    const origin = event.clientX;
    const move = (ev: PointerEvent) => setExpandedWidth(from + (ev.clientX - origin) * ratio, false);
    const done = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", done);
      grip.removeEventListener("pointercancel", done);
      root.classList.remove("da-panel-resizing");
      setExpandedWidth(expandedWidth); // 松手才落盘
    };
    grip.setPointerCapture(event.pointerId);
    root.classList.add("da-panel-resizing");
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", done);
    grip.addEventListener("pointercancel", done);
  });

  grip.addEventListener("keydown", (event) => {
    const delta = event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
    if (!delta) return;
    event.preventDefault();
    setExpandedWidth(expandedWidth + delta * (event.shiftKey ? 64 : 16) * ratio);
  });
}
