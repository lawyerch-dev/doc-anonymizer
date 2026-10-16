import { useEffect, useState } from "react";

/**
 * 读一条媒体查询的匹配状态, 并跟随窗口变化。
 *
 * 识别统计面板要在"宽屏进右栏 / 窄屏回左栏"之间搬位置 —— 这是 DOM 层面的搬移,
 * CSS 断点做不到; 但同一个面板不能在两处各挂一份(id 会撞), 所以用 JS 断点做单实例开关。
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}
