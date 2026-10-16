/**
 * 选文件夹相关的浏览器探测与 JSX 补丁 —— 之前 App / PresetList / RestorePanel 各自写一份。
 *
 * `webkitdirectory` 在 Safari/Chromium 上都有, 但 **WKWebView(桌面壳)未必放行**: 探测一次,
 * 没有就不显示入口, 而不是点了一下什么都不发生。
 */
export const HAS_FOLDER_PICKER =
  typeof HTMLInputElement !== "undefined" && "webkitdirectory" in HTMLInputElement.prototype;

/** React 的 JSX 类型里没有 `webkitdirectory`/`directory` 这两个前缀属性, 只能这样塞给 `<input>`。 */
export const DIRECTORY_INPUT_PROPS = { webkitdirectory: "", directory: "" } as Record<string, string>;
