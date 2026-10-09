import { TEXT_EXT } from "./formats";

export type ViewerOptions = {
  theme?: string;
  toolbar?: boolean;
  pdf?: { toolbar?: boolean; navigation?: boolean };
};

type FlyfishViewer = {
  setDefaultFullAssetBaseUrl?: (base: string) => void;
  mountViewer?: (
    el: HTMLElement,
    opts: { url: string; filename: string; options?: ViewerOptions },
  ) => void;
};

declare global {
  interface Window {
    FlyfishFileViewerWebFull?: FlyfishViewer;
  }
}

/** 文本类自己渲染(与旧 app.js 的 TEXT_EXT 分支一致) */
async function showText(el: HTMLElement, url: string): Promise<void> {
  try {
    const text = await (await fetch(url)).text();
    const pre = document.createElement("pre");
    pre.className =
      "m-0 h-full overflow-auto whitespace-pre-wrap break-all bg-card p-4 text-[13px] leading-relaxed";
    pre.textContent = text;
    el.replaceChildren(pre);
  } catch (e) {
    el.textContent = `无法预览: ${(e as Error).message}`;
  }
}

/**
 * 把文档挂进 container。文本类走 <pre>，其余交给 file-viewer；
 * file-viewer 挂载失败时回退到文本预览(readable 总比空白强)。
 */
export function mountViewer(container: HTMLElement, url: string, filename: string): void {
  const FV = window.FlyfishFileViewerWebFull;
  if (FV?.setDefaultFullAssetBaseUrl) {
    FV.setDefaultFullAssetBaseUrl(new URL("/file-viewer/", location.href).href);
  }

  const host = document.createElement("div");
  host.className = "absolute inset-0";
  container.replaceChildren(host);

  const ext = (filename.split(".").pop() || "").toLowerCase();
  if (TEXT_EXT.includes(ext)) {
    void showText(host, url);
    return;
  }

  if (FV?.mountViewer) {
    try {
      FV.mountViewer(host, {
        url: new URL(url, location.href).href,
        filename,
        // theme 必须放 options 里(顶层会被忽略); pdf.toolbar/navigation 关掉内部工具栏/缩略图,
        // 否则窄窗格横向溢出、re-fit 抖动(与旧 app.js 同因)
        options: { theme: "light", toolbar: false, pdf: { toolbar: false, navigation: false } },
      });
      return;
    } catch (e) {
      console.warn("file-viewer mount failed", e);
    }
  }
  void showText(host, url);
}

export function clearViewer(container: HTMLElement | null): void {
  container?.replaceChildren();
}
