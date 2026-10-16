import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// dev 期把后端的前缀转发过去(docanon web 默认 8000); 生产不走这里(dist 由 docanon web 直发)
// `/restored/` 是还原件目录 —— 少这一条, 还原做完了却下载不到文件(实测踩过: 面板给的是 404 链接)
const BACKEND = process.env.DOCANON_BACKEND || "http://127.0.0.1:8000";
const PROXIED = ["/api", "/samples", "/uploads", "/outputs", "/restored", "/file-viewer", "/health"];

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 产物落 apps/web/dist: 与源码不同层, emptyOutDir 可安全清空(不会覆盖源码)
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5173,
    // 口被占就报错退出, 不许悄悄换到 5174: dev.sh 提示的是 5173, 换口等于"照提示打开的是旧进程"
    // (踩过一次: 上次残留的 Vite 占着 5173, 新的跑到 5174, 页面看着能开其实没连上后端)
    strictPort: true,
    // 绑 IPv4: 默认的 `localhost` 在 macOS + Node 上常常只监听 [::1], 而 README/quickstart/dev.sh
    // 让我们开 http://127.0.0.1:5173 —— 不显式绑就会"照文档打不开"
    host: "127.0.0.1",
    // HMR 的 ws 也显式走 IPv4: 页面按 localhost 打开时, @vite/client 默认按页面 origin 连 ws,
    // 会先试 [::1] 而服务只绑了 127.0.0.1 —— 于是控制台刷 "failed to connect to websocket"
    hmr: { host: "127.0.0.1", protocol: "ws" },
    proxy: Object.fromEntries(PROXIED.map((p) => [p, { target: BACKEND }])),
  },
});
