/**
 * 在 WebKit 引擎(macOS 上即 Safari / WKWebView 的内核)里跑一遍 Web UI，
 * 验证 file-viewer 的预览、脱敏、前后对比是否正常，并收集控制台错误。
 *
 * 用法: DOCANON_URL=http://127.0.0.1:8803 [PRESET=sample_text.pdf] node webkit-check.mjs
 */
import { webkit } from 'playwright';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const URL = process.env.DOCANON_URL || 'http://127.0.0.1:8803';
const PRESET = process.env.PRESET || 'sample.docx';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/** zip 里的条目名 + 是否标了 UTF-8。
 *
 * 自己读中央目录而不是调 `unzip`: macOS 的 unzip 打印名字时会按本地编码再转一道(中文变乱码),
 * 拿它断言等于在测 unzip 的显示, 不是测我们的包。
 */
function zipEntries(file) {
  const buf = fs.readFileSync(file);
  const out = [];
  for (let i = 0; i + 46 <= buf.length; i++) {
    if (buf.readUInt32LE(i) !== 0x02014b50) continue; // 中央目录项签名
    const flags = buf.readUInt16LE(i + 8);
    const nameLen = buf.readUInt16LE(i + 28);
    const extraLen = buf.readUInt16LE(i + 30);
    const commentLen = buf.readUInt16LE(i + 32);
    out.push({
      name: buf.subarray(i + 46, i + 46 + nameLen).toString('utf8'),
      utf8: Boolean(flags & 0x800),
    });
    i += 45 + nameLen + extraLen + commentLen; // 跳到本项末尾(循环再 i++ 正好落到下一项)
  }
  return out;
}

const browser = await webkit.launch();
const page = await browser.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message));

await page.addInitScript(() => { localStorage.setItem('docanon.onboarded', '1'); });
await page.goto(URL, { waitUntil: 'domcontentloaded' });
// 示例不再自动加载: 先点「加载示例」再等 .preset 出现
await page.locator('#loadSamples').click();
await page.waitForSelector('.preset', { timeout: 15000 });
await page.locator('.preset', { hasText: PRESET }).click();
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

console.log(JSON.stringify({ preset: PRESET, render: before, after, errors: errors.slice(0, 20) }, null, 1));

// ---- 选文件夹(批量): 上传 → 跑批 → 每份状态 → 点已处理的看对比 → 整包下载 ----
// 夹具现造: 两个能跑的(其中一份在子目录里, 中文名) + 一个不支持的类型 + 一个隐藏项。
// 断言的正是那几条硬约束: 隐藏项不进列表、不支持的必须露面(不静默丢)、产物保留相对目录、包里没有映射表。
const FOLDER = fs.mkdtempSync(path.join(os.tmpdir(), 'docanon-folder-'));
fs.mkdirSync(path.join(FOLDER, '合同'), { recursive: true });
fs.writeFileSync(path.join(FOLDER, '合同', '附件A.txt'), '张三 13812340000\n');
fs.writeFileSync(path.join(FOLDER, '说明.md'), '联系 李四 13998765432\n');
fs.writeFileSync(path.join(FOLDER, '图.psd'), Buffer.from([0x38, 0x42, 0x50, 0x53]));
fs.writeFileSync(path.join(FOLDER, '.DS_Store'), 'junk');

await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('#pickFolder');
await page.locator('#pickFolder').click();
await page.locator('input[webkitdirectory]').setInputFiles(FOLDER);
await page.waitForSelector('.doc-row', { timeout: 30000 });
await page.waitForFunction(
  () => !document.querySelector('#pickFolder')?.textContent?.includes('上传中'), null, { timeout: 60000 },
);

const rowsAfterUpload = await page.$$eval('.doc-row', (els) =>
  els.map((e) => ({ name: e.querySelector('span:nth-of-type(2)')?.textContent?.trim(), status: e.dataset.status })));

await page.locator('#run').click();
await page.waitForSelector('.doc-row[data-status=ok]', { timeout: 180000 });
await wait(1000);
const rowsAfterRun = await page.$$eval('.doc-row', (els) =>
  els.map((e) => ({ name: e.querySelector('span:nth-of-type(2)')?.textContent?.trim(), status: e.dataset.status })));
const summary = (await page.locator('#batchSummary').innerText()).replace(/\s+/g, ' ').trim();

// 点"未处理"那行: 右栏要说原因, 不是一片空白对比
await page.locator('.doc-row[data-status=unsupported]').first().click();
await wait(500);
const blockedHint = (await page.locator('#paneOut .placeholder').innerText()).replace(/\s+/g, ' ').trim();

// 点"已脱敏"那行: 右栏真出内容
await page.locator('.doc-row[data-status=ok]').first().click();
await wait(2000);
const okPaneHasContent = await page.locator('#paneOut .placeholder').count() === 0;

let zip = null;
if (await page.locator('#downloadZip').count()) {
  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 60000 }),
    page.locator('#downloadZip').click(),
  ]);
  const saved = path.join(os.tmpdir(), 'docanon-webkit-check.zip');
  await download.saveAs(saved);
  zip = { name: download.suggestedFilename(), entries: zipEntries(saved) };
}

console.log(JSON.stringify({
  folder: {
    uploadRows: rowsAfterUpload, runRows: rowsAfterRun, summary,
    blockedHint, okPaneHasContent, zip,
    expected: {
      uploadRows: 3, // 两个可跑 + 一个 .psd; .DS_Store 不算
      unsupportedShown: true, hiddenSkipped: true, zipHasNoMapping: true, zipKeepsSubdir: true,
    },
  },
  errors: errors.slice(0, 20),
}, null, 1));
await fs.rmSync(FOLDER, { recursive: true, force: true });
await browser.close();
