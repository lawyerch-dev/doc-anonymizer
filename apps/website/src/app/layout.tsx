import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "doc-anonymizer 文档",
  description: "本地文档脱敏：中文优先、全离线、保留原格式（CLI + Web + 桌面壳）",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      {/* 用系统字体栈: 构建期不拉 Google Fonts, 离线也能 build */}
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}
