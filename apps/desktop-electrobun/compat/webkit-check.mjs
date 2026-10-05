/**
 * 在 WebKit 引擎(macOS 上即 Safari / WKWebView 的内核)里跑一遍 Web UI，
 * 验证 file-viewer 的预览、脱敏、前后对比是否正常，并收集控制台错误。
 *
 * 用法: DOCANON_URL=http://127.0.0.1:8803 node webkit-check.mjs
 */
import { webkit } from 'playwright';

const URL = process.env.DOCANON_URL || 'http://127.0.0.1:8803';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await webkit.launch();
const page = await browser.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message));

await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('.preset', { timeout: 15000 });
await page.locator('.preset', { hasText: 'sample.docx' }).click();
await wait(7000);

const shadowProbe = () => {
  const find = (n) => {
    if (n.shadowRoot) return n.shadowRoot;
    for (const c of n.children) { const s = find(c); if (s) return s; }
    return null;
  };
  const r = (id) => {
    const host = document.getElementById(id)?.firstElementChild;
    const sr = host && find(host);
    return sr ? { nodes: sr.querySelectorAll('*').length, text: (sr.textContent || '').replace(/\s+/g, ' ').slice(0, 120) } : null;
  };
  const shell = (() => {
    const host = document.getElementById('paneSrc')?.firstElementChild;
    const sr = host && find(host);
    return sr ? sr.querySelector('.file-viewer-web-shell') : null;
  })();
  return { src: r('paneSrc'), out: r('paneOut'), theme: shell ? shell.getAttribute('data-viewer-theme') : null };
};

const before = await page.evaluate(shadowProbe);
await page.locator('#run').click();
await wait(7000);
const after = await page.evaluate(() => {
  const find = (n) => {
    if (n.shadowRoot) return n.shadowRoot;
    for (const c of n.children) { const s = find(c); if (s) return s; }
    return null;
  };
  const host = document.getElementById('paneOut')?.firstElementChild;
  const sr = host && find(host);
  return {
    outNodes: sr ? sr.querySelectorAll('*').length : 0,
    stats: document.getElementById('stats').textContent.replace(/\s+/g, ' ').trim(),
    eng: navigator.userAgent,
  };
});

console.log(JSON.stringify({ render: before, after, errors: errors.slice(0, 20) }, null, 1));
await browser.close();
