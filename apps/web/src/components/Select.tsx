import type { ReactNode, SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  children: ReactNode;
  /** 外层那圈的类(宽度等): 默认按内容宽, 要撑满传 "w-full" */
  wrapperClassName?: string;
};

/**
 * 下拉框的统一皮。
 *
 * 为什么不是自搓一个"下拉": 原生 `<select>` 的键盘、输入法、无障碍(Safari/VoiceOver 那一套)
 * 都是自带的, 自己拼一个要补的东西太多。这里只换**外观** —— 浏览器默认那套控件样式(尤其 macOS
 * 的圆角箭头)跟这套设计不是一家人, 所以套上与 `Input` 同一套边框/焦点环, 再自己画个箭头。
 *
 * 为什么不用组件库: `packages/ui` 里没有 select 这一档(只有 accordion/button/dialog/dropdown-menu/
 * input/label/sheet/tabs/avatar/badge), 为一个下拉去跑 `shadcn add` 拉一整套不值得。
 */
export function Select({ className = "", wrapperClassName = "", children, ...rest }: Props) {
  return (
    <span className={`relative inline-flex items-center ${wrapperClassName}`}>
      <select
        {...rest}
        className={`w-full appearance-none rounded-lg border border-input bg-background py-1.5 pr-7 pl-2.5 text-sm transition-colors outline-none hover:bg-accent/40 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 ${className}`}
      >
        {children}
      </select>
      <svg
        className="pointer-events-none absolute right-2 size-3.5 shrink-0 opacity-60"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </span>
  );
}
