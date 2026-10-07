/**
 * 抖动诊断: 在 WebKit 引擎(Safari/WKWebView 内同核)里打开 PDF 预览,
 * 量化 3 秒内的 DOM 变更 / 尺寸变化 / 滚动位置变化 / 主题属性抖动。
 *
 * 用法: DOCANON_URL=http://127.0.0.1:8803 PRESET=sample_text.pdf node jitter-check.mjs
 */
import { webkit } from 'playwright';

const URL = process.env.DOCANON_URL || 'http://127.0.0.1:8803';
const PRESET = process.env.PRESET || 'sample_text.pdf';

const browser = await webkit.launch();
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message));

await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.preset', { timeout: 15000 });
await page.evaluate((p) => { window.__PRESET = p; }, PRESET);

const res = await page.evaluate(async () => {
  const find = (n) => {
    if (n.shadowRoot) return n.shadowRoot;
    for (const c of n.children) { const s = find(c); if (s) return s; }
    return null;
  };
  const presetEl = [...document.querySelectorAll('.preset')].find((e) => e.textContent.includes(window.__PRESET));
  presetEl?.click();
  const host = document.getElementById('paneSrc')?.firstElementChild;
  // 等待 shadow 出现
  let sr = null, shell = null;
  for (let i = 0; i < 60; i++) {
    sr = host && find(host);
    shell = sr && sr.querySelector('.file-viewer-web-shell');
    if (shell) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!sr) return { error: 'no shadow' };

  let mutations = 0, childList = 0, attrs = 0, themeFlips = 0;
  const themeSeq = [];
  const mo = new MutationObserver((ms) => {
    mutations += ms.length;
    for (const m of ms) {
      if (m.type === 'childList') childList++;
      else {
        attrs++;
        if (m.attributeName === 'data-viewer-theme') { themeFlips++; themeSeq.push(shell?.getAttribute('data-viewer-theme')); }
      }
    }
  });
  mo.observe(sr, { subtree: true, childList: true, attributes: true });

  let resizes = 0;
  let ro;
  if (shell && window.ResizeObserver) { ro = new ResizeObserver(() => resizes++); ro.observe(shell); }

  const scrollUnique = new Set();
  const dimsUnique = new Set();
  const iv = setInterval(() => {
    const all = sr.querySelectorAll('*');
    for (const el of all) { if (el.scrollHeight > el.clientHeight + 4 && el.clientHeight > 100) { scrollUnique.add(Math.round(el.scrollTop)); break; } }
    if (shell) { const r = shell.getBoundingClientRect(); dimsUnique.add(Math.round(r.width) + 'x' + Math.round(r.height)); }
  }, 80);

  await new Promise((r) => setTimeout(r, 8000)); // 覆盖加载+自适应瞬态
  clearInterval(iv); mo.disconnect(); ro && ro.disconnect();

  return {
    mutations8s: mutations, childList, attrs,
    themeFlips, themeSeq: [...new Set(themeSeq)].slice(0, 6),
    resizes8s: resizes,
    scrollUnique: [...scrollUnique].slice(0, 12),
    dimsUnique: [...dimsUnique].slice(0, 12),
  };
});

console.log(JSON.stringify({ preset: PRESET, ...res, errors: errors.slice(0, 8) }, null, 1));
await browser.close();
