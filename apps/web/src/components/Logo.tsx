/**
 * 品牌标: 盾牌 + 一条被"抹掉"的横条 —— 盾=本地不出网, 缺口的横条=把敏感信息抹掉。
 *
 * 为什么是内联 SVG 而不是图片文件: 这个项目**运行期全离线**, 用在线图片 URL 会让界面一开就联网;
 * 而 PNG/SVG 文件又要走 file-viewer 之外的静态服务。内联 SVG 零请求、零依赖, 颜色还能直接吃
 * 主题 token(`brand` 渐变), 明暗两态自动跟着走。
 */
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      role="img"
      aria-label="文档脱敏工具"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="logo-brand" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--brand-from)" />
          <stop offset="50%" stopColor="var(--brand-via)" />
          <stop offset="100%" stopColor="var(--brand-to)" />
        </linearGradient>
      </defs>
      {/* 盾牌轮廓 */}
      <path
        d="M16 2.5 27.5 6.6v9.1c0 7.3-4.8 12.3-11.5 14.8C9.3 28 4.5 23 4.5 15.7V6.6L16 2.5Z"
        fill="url(#logo-brand)"
      />
      {/* 文稿上的几行字(浅色条纹) + 中间那条"已被抹掉"的实心条 */}
      <path d="M10.5 11h7" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity=".75" />
      <path d="M10.5 16h11" stroke="white" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M10.5 21h7" stroke="white" strokeWidth="1.8" strokeLinecap="round" opacity=".75" />
    </svg>
  );
}
