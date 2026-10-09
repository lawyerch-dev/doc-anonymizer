import { useEffect, useRef } from "react";
import { clearViewer, mountViewer } from "../lib/viewer";

type Props = {
  /** "src" | "out": 决定 E2E 依赖的容器 id */
  pane: "src" | "out";
  title: string;
  filename: string;
  url: string;
  placeholder: string;
  action?: { label: string; href: string };
};

export function Preview({ pane, title, filename, url, placeholder, action }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    if (!url) {
      clearViewer(el);
      return () => clearViewer(el);
    }
    mountViewer(el, url, filename);
    return () => clearViewer(el);
  }, [url, filename]);

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border bg-card">
      <div className="flex min-h-11 items-center gap-2.5 border-b px-3.5 py-2 text-[13px]">
        <b className="font-semibold">{title}</b>
        <span className="truncate text-muted-foreground">{filename}</span>
        <span className="ml-auto flex gap-2">
          {action && url ? (
            <a href={action.href} download className="inline-flex">
              <span className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
                {action.label}
              </span>
            </a>
          ) : null}
        </span>
      </div>
      <div id={pane === "src" ? "paneSrc" : "paneOut"} className="relative min-h-0 flex-1 overflow-hidden">
        {url ? (
          <div ref={hostRef} className="absolute inset-0" />
        ) : (
          <div className="placeholder absolute inset-0 flex flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            {placeholder}
          </div>
        )}
      </div>
    </section>
  );
}
