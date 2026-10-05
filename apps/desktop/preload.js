/** 预加载脚本: 目前无需向页面暴露额外能力, 保留 contextIsolation 安全默认。 */
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('docanonShell', {
  platform: process.platform,
  version: '0.1.0',
});
