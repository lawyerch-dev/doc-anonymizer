import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// dev 期把后端的六条前缀(/api /samples /uploads /outputs /file-viewer /health)转发过去(docanon web 默认 8000); 生产不走这里(dist 由 docanon web 直发)
const BACKEND = process.env.DOCANON_BACKEND || "http://127.0.0.1:8000";
const PROXIED = ["/api", "/samples", "/uploads", "/outputs", "/file-viewer", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 产物落 apps/web/dist: 与源码不同层, emptyOutDir 可安全清空(不会覆盖源码)
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    // 绑 IPv4: 默认的 `localhost` 在 macOS + Node 上常常只监听 [::1], 而 README/quickstart/dev.sh
    // 让我们开 http://127.0.0.1:5173 —— 不显式绑就会"照文档打不开"
    host: "127.0.0.1",
    proxy: Object.fromEntries(PROXIED.map((p) => [p, { target: BACKEND }])),
  },
});
