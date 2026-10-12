import { useEffect, useState } from "react";
import { ThemeToggler } from "@doc-anonymizer/ui/theme-toggler";

/**
 * 落地页的主题开关。与文档站(Starlight)共用 `starlight-theme` 这一处存储 ——
 * 两边切到哪套, 另一处打开时跟着走, 不会一站两制。
 *
 * 首屏防闪由 `LandingPage.astro` 的 head 内联脚本负责(它先于任何样式跑);
 * 这里只管点击后的切换与写回。挂载前渲染同尺寸占位, 免得服务端不知道
 * 访客的 localStorage 而先画错一个图标。
 */
const STORAGE_KEY = "starlight-theme";

function apply(dark: boolean) {
  const root = document.documentElement;
  root.classList.toggle("dark", dark);
  root.dataset.theme = dark ? "dark" : "light";
}

export default function ThemeSwitch() {
  const [mounted, setMounted] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
    setMounted(true);
  }, []);

  if (!mounted) return <span className="size-9" aria-hidden />;

  const toggle = () => {
    const next = !isDark;
    apply(next);
    localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
    setIsDark(next);
  };

  return <ThemeToggler isDark={isDark} onToggle={toggle} />;
}
