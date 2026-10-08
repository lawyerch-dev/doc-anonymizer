// @ts-check
/* 文档脱敏工具 Web UI 逻辑 —— 零构建: 普通(非 module)脚本, 由 docanon web 直接发出去。
   必须在 body 末尾、且在 file-viewer 的 <script> 之后加载(解析期就会绑定事件并拉预设)。
   `// @ts-check` + 下面的 JSDoc: 编辑器能按类型提示, 但不需要任何构建链。 */

/** @typedef {{name:string, url:string, size:number, preview:boolean}} Preset */
/** @typedef {{entity_type:string, source:string, strategy:string, original:string,
 *             replacement?:string, locator:Record<string, any>}} Detection */
/** @typedef {{source:string, extractor:string, converted_from?:string, config?:string,
 *             detectors:string[], timing:Record<string, number>, detections:Detection[]}} Trace */
/** @typedef {{output_name:string, output_url:string, counts:Record<string, number>,
 *             kind:string, trace?:Trace, error?:string}} AnonymizeResp */
/** @typedef {{token:string, filename:string, url:string, error?:string}} UploadResp */

const FV = window.FlyfishFileViewerWebFull;
if (FV && FV.setDefaultFullAssetBaseUrl) FV.setDefaultFullAssetBaseUrl(new URL('/file-viewer/', location.href).href);

const state = { preset: null, token: null, filename: null, url: null, trace: null, logOpen: false, configRef: null, configData: null, configDirty: false, modelDirs: null };
const $ = id => document.getElementById(id);
function markDirty() { state.configDirty = true; }
const TEXT_EXT = ['txt', 'md', 'markdown', 'csv'];

function mount(containerId, url, filename) {
  const el = $(containerId);
  el.innerHTML = '';
  const inner = document.createElement('div');
  inner.style.position = 'absolute'; inner.style.inset = '0';
  el.appendChild(inner);
  const ext = (filename.split('.').pop() || '').toLowerCase();
  if (TEXT_EXT.includes(ext)) { return showText(inner, url); }
  if (FV && FV.mountViewer) {
    try {
      FV.mountViewer(inner, {
        url: new URL(url, location.href).href,
        filename,
        // theme 必须放 options 里(顶层会被忽略); toolbar:false 关外层工具栏;
        // pdf.toolbar/navigation 关 PDF 内部工具栏/缩略图栏(否则窄窗格横向溢出、re-fit 抖动)。
        options: { theme: 'light', toolbar: false, pdf: { toolbar: false, navigation: false } },
      });
      return;
    } catch (e) { console.warn('file-viewer mount failed', e); }
  }
  showText(inner, url);
}

async function showText(el, url) {
  try {
    const r = await fetch(url);
    const t = await r.text();
    const pre = document.createElement('pre');
    pre.className = 'raw'; pre.textContent = t;
    el.appendChild(pre);
  } catch (e) {
    el.innerHTML = '<div class="placeholder">无法预览: ' + e.message + '</div>';
  }
}

function resetOutput() {
  state.trace = null;
  $('outName').textContent = '';
  $('dlOut').classList.add('hidden');
  $('paneOut').innerHTML = '<div class="placeholder">点击「开始脱敏」查看结果</div>';
  $('statsCard').classList.add('hidden');
  $('logModal').classList.add('hidden');
  $('toggleLog').disabled = true;
}

function selectDoc({ preset, token, filename, url }) {
  state.preset = preset; state.token = token;
  state.filename = filename; state.url = url;
  $('srcName').textContent = filename;
  $('dlSrc').href = url; $('dlSrc').classList.remove('hidden');
  $('run').disabled = false;
  resetOutput();
  $('opDetails').textContent = '已选择: ' + filename;
  mount('paneSrc', url, filename);
}

function selectPreset(p, node) {
  document.querySelectorAll('.preset').forEach(n => n.classList.remove('active'));
  node.classList.add('active');
  selectDoc({ preset: p.name, token: null, filename: p.name, url: p.url });
}

async function loadPresets() {
  const box = $('presets');
  const btn = $('refresh');
  if (btn) { btn.disabled = true; }
  box.innerHTML = '<div class="hint">加载中…</div>';
  try {
    const { presets } = await (await fetch('/api/presets', { cache: 'no-store' })).json();
    box.innerHTML = '';
    if (!presets.length) { box.innerHTML = '<div class="hint">samples/ 无可预览示例</div>'; return; }
    presets.forEach(p => {
      const n = document.createElement('div');
      n.className = 'preset';
      n.title = p.name;
      n.innerHTML = '<span>📄</span><span>' + p.name + '</span><span class="tag">' +
        (p.name.split('.').pop()) + '</span>';
      n.onclick = () => selectPreset(p, n);
      box.appendChild(n);
    });
  } catch (e) {
    box.innerHTML = '<div class="hint">加载失败: ' + e.message + '</div>';
  } finally {
    if (btn) { btn.disabled = false; }
  }
}

$('refresh').onclick = loadPresets;

async function loadConfigs() {
  const sel = $('cfgSel');
  try {
    const { configs } = await (await fetch('/api/configs', { cache: 'no-store' })).json();
    sel.innerHTML = '';
    configs.forEach(c => {
      const o = document.createElement('option');
      o.value = c.name;
      o.textContent = c.label + (c.kind === 'user' ? '（我的）' : '') + (c.current ? '（当前）' : '');
      sel.appendChild(o);
    });
    const saved = localStorage.getItem('docanon.config');
    const pick = configs.find(c => c.name === saved) || configs.find(c => c.current) || configs[0];
    sel.onchange = () => { localStorage.setItem('docanon.config', sel.value); loadConfigData(sel.value); };
    if (pick) { sel.value = pick.name; await loadConfigData(pick.name); }
  } catch (e) {
    sel.innerHTML = '<option>配置加载失败</option>';
  }
}

const ENTITY_TYPES = ['PHONE','ID_CARD','PASSPORT','PLATE','BANK_CARD','EMAIL','IP','USCC',
  'PERSON','ORG','LOCATION','AMOUNT','DOB','SECRET','CUSTOM','DEFAULT'];
const STRATEGIES = ['redact','mask','placeholder','pseudonym','remove','keep'];
const EFFECT = { redact: '**', mask: '138****0000', placeholder: '<PHONE_1>',
  pseudonym: '林芳', remove: '（删除）', keep: '（不动）' };

function renderEditors() {
  const d = state.configData;
  if (!d) return;
  d.strategies = d.strategies || {};
  d.detectors = d.detectors || {};
  d.onnx = d.onnx || { model_dirs: [] };
  d.llm = d.llm || {};
  // L2 策略表: 未列出的类型走后端同款 DEFAULT 兜底(不是硬编码 redact)
  const DEF = d.strategies.DEFAULT || 'placeholder';
  const rows = ENTITY_TYPES.map(t => {
    const cur = (t in d.strategies) ? d.strategies[t] : DEF;
    const opts = STRATEGIES.map(s => '<option value="' + s + '"' + (s === cur ? ' selected' : '') + '>' + s + '</option>').join('');
    return '<tr><td>' + t + '</td><td><select data-entity="' + t + '">' + opts + '</select></td>' +
      '<td class="hint">' + EFFECT[cur] + '</td></tr>';
  }).join('');
  $('stratTable').innerHTML = '<tr><th>类型</th><th>策略</th><th>效果</th></tr>' + rows;
  $('stratTable').querySelectorAll('select[data-entity]').forEach(sel => {
    sel.onchange = () => {
      state.configData.strategies[sel.dataset.entity] = sel.value;
      markDirty();
      renderEditors();
    };
  });
  // 假名开关: 依据 PERSON/ORG 的生效策略(含 DEFAULT 兜底)是否 pseudonym 反推
  const effPerson = ('PERSON' in d.strategies) ? d.strategies.PERSON : DEF;
  const effOrg = ('ORG' in d.strategies) ? d.strategies.ORG : DEF;
  $('fakeNames').checked = effPerson === 'pseudonym' && effOrg === 'pseudonym';
  $('fakeNames').onchange = () => {
    const v = $('fakeNames').checked ? 'pseudonym' : 'redact';
    d.strategies.PERSON = v; d.strategies.ORG = v;
    markDirty();
    renderEditors();
  };
  // 词典
  $('dictInput').value = (d.dictionary || []).join('，');
  $('dictInput').onchange = () => {
    state.configData.dictionary = $('dictInput').value.split(/[，,]/).map(s => s.trim()).filter(Boolean);
    markDirty();
  };
  // L3 检测器
  $('detBox').innerHTML = ['rule','dictionary','onnx_ner','llm_ner'].map(n =>
    '<label style="display:block"><input type="checkbox" data-det="' + n + '"' +
    (d.detectors[n] ? ' checked' : '') + '> ' + n + '</label>').join('');
  $('detBox').querySelectorAll('input[data-det]').forEach(cb => {
    cb.onchange = () => { state.configData.detectors[cb.dataset.det] = cb.checked; markDirty(); };
  });
  $('llmUrl').value = (d.llm && d.llm.base_url) || '';
  $('llmUrl').onchange = () => { state.configData.llm.base_url = $('llmUrl').value; markDirty(); };
  $('llmModel').value = (d.llm && d.llm.model) || '';
  $('llmModel').onchange = () => { state.configData.llm.model = $('llmModel').value; markDirty(); };
  loadModelDirs();
}

async function loadModelDirs() {
  if (state.modelDirs === null) {
    try {
      const { onnx_dirs } = await (await fetch('/api/models', { cache: 'no-store' })).json();
      state.modelDirs = onnx_dirs;
    } catch (e) {
      state.modelDirs = []; /* 无模型目录时静默留空 */
    }
  }
  renderModelDirs();
}

function renderModelDirs() {
  const chosen = new Set((state.configData.onnx && state.configData.onnx.model_dirs) || []);
  $('modelDirs').innerHTML = state.modelDirs.map(d =>
    '<option value="' + d + '"' + (chosen.has(d) ? ' selected' : '') + '>' + d + '</option>').join('');
  $('modelDirs').onchange = () => {
    state.configData.onnx.model_dirs = Array.from($('modelDirs').selectedOptions).map(o => o.value);
    markDirty();
  };
}

async function saveConfig() {
  const name = prompt('配置名（字母/数字/下划线/连字符）:', state.configRef && !state.configRef.endsWith('.yaml') ? state.configRef : 'my-config');
  if (!name) return;
  const r = await fetch('/api/configs/' + encodeURIComponent(name), {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state.configData),
  });
  const body = await r.json();
  if (body.error) { showErr('保存失败: ' + body.error); return; }
  localStorage.setItem('docanon.config', name);
  await loadConfigs();
}

$('saveCfg').onclick = saveConfig;
$('exportCfg').onclick = () => { if (state.configRef) location.href = '/api/configs/' + encodeURIComponent(state.configRef) + '/export'; };
$('importCfg').onclick = () => $('cfgFile').click();
$('cfgFile').onchange = async () => {
  const f = $('cfgFile').files[0]; if (!f) return;
  const buf = new Uint8Array(await f.arrayBuffer());
  let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  const r = await fetch('/api/configs/import', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename: f.name, content_b64: btoa(s) }) });
  const body = await r.json();
  if (body.error) { showErr('导入失败: ' + body.error); return; }
  await loadConfigs();
};

async function loadConfigData(ref) {
  try {
    const body = await (await fetch('/api/configs/' + encodeURIComponent(ref), { cache: 'no-store' })).json();
    if (body.error) throw new Error(body.error);
    state.configRef = ref;
    state.configData = body.data;
    state.configDirty = false;
    $('cfgMeta').textContent = ref + (body.kind === 'user' ? ' · 我的配置' : ' · 内置');
    if (typeof renderEditors === 'function') renderEditors();
  } catch (e) {
    state.configRef = null;
    state.configData = null;
    $('cfgMeta').textContent = '读取失败: ' + e.message;
  }
}

$('upload').onclick = () => $('file').click();
$('file').onchange = async () => {
  const f = $('file').files[0]; if (!f) return;
  const btn = $('upload'); btn.disabled = true; const old = btn.textContent; btn.textContent = '上传中…';
  try {
    const buf = new Uint8Array(await f.arrayBuffer());
    let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    const resp = await (await fetch('/api/upload', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: f.name, content_b64: btoa(s) }) })).json();
    if (resp.error) throw new Error(resp.error);
    document.querySelectorAll('.preset').forEach(n => n.classList.remove('active'));
    selectDoc({ preset: null, token: resp.token, filename: resp.filename, url: resp.url });
  } catch (e) {
    showErr('上传失败: ' + e.message);
  } finally { btn.disabled = false; btn.textContent = old; }
};

$('run').onclick = async () => {
  const btn = $('run'); btn.disabled = true; btn.innerHTML = '<span class="spin"></span> 脱敏中';
  $('err').classList.add('hidden');
  try {
    const body = state.preset ? { preset: state.preset } : { token: state.token };
    // 未编辑 → 发口径名(日志显示真实口径); 编辑后 → 发内联对象。Task 8 任何编辑须置 state.configDirty = true。
    if (state.configData && state.configDirty) { body.config = state.configData; }
    else if (state.configRef) { body.config = state.configRef; }
    const resp = await (await fetch('/api/anonymize', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body) })).json();
    if (resp.error) throw new Error(resp.error);
    $('outName').textContent = resp.output_name;
    $('dlOut').href = resp.output_url; $('dlOut').classList.remove('hidden');
    mount('paneOut', resp.output_url, resp.output_name);
    renderStats(resp.counts);
    state.trace = resp.trace || null;
    renderOpDetails(resp);
    $('toggleLog').disabled = !state.trace;
    $('logModal').classList.add('hidden');
  } catch (e) {
    showErr('脱敏失败: ' + e.message);
  } finally { btn.disabled = false; btn.textContent = '开始脱敏'; }
};

$('toggleLog').onclick = () => {
  if (!state.trace) return;
  renderLog(state.trace);
  $('logModal').classList.remove('hidden');
};
$('logClose').onclick = () => $('logModal').classList.add('hidden');
$('logModal').onclick = (e) => { if (e.target === $('logModal')) $('logModal').classList.add('hidden'); };

function totalCounts(counts) { return Object.values(counts || {}).reduce((a, b) => a + b, 0); }

function renderOpDetails(resp) {
  const c = resp.counts || {};
  const types = Object.keys(c).join('+') || '无命中';
  const t = (resp.trace && resp.trace.timing) || {};
  const ms = t.total_ms != null ? Math.round(t.total_ms) + 'ms' : '';
  const converted = resp.trace && resp.trace.converted_from;
  $('opDetails').textContent =
    '已脱敏 ' + resp.output_name + ' · 类型 ' + types + ' · 命中 ' + totalCounts(c) + ' · ' + ms +
    (converted ? ' · 已由 ' + converted + ' 转换, 版式可能被重排' : '');
  $('opDetails').title = JSON.stringify(c);
}

function renderLog(tr) {
  const t = tr.timing || {};
  const kept = (tr.detections || []).filter(d => d.strategy === 'keep');
  const keptCounts = {};
  kept.forEach(d => { keptCounts[d.entity_type] = (keptCounts[d.entity_type] || 0) + 1; });
  const keptText = kept.length
    ? '<br>按配置保留 <b>' + kept.length + '</b> 处（' +
      Object.entries(keptCounts).map(kv => esc(kv[0]) + '×' + kv[1]).join('、') +
      '）—— 识别到了，但这几类不在你的脱敏范围'
    : '';
  const meta =
    '<div class="meta">' +
    '源文件 <code>' + esc(tr.source) + '</code> · 抽取器 <code>' + esc(tr.extractor) + '</code> · ' +
    (tr.converted_from
      ? '已由 <code>' + esc(tr.converted_from) + '</code> 转换(版式可能被重排) · '
      : '') +
    (tr.config ? '口径 <code>' + esc(tr.config) + '</code> · ' : '') +
    '检测器 <code>' + esc((tr.detectors || []).join(' + ')) + '</code><br>' +
    '耗时: 抽取 ' + (t.extract_ms ?? '-') + 'ms · 检测 ' + (t.detect_ms ?? '-') + 'ms · ' +
    '回写 ' + (t.write_ms ?? '-') + 'ms · 合计 <b>' + (t.total_ms ?? '-') + 'ms</b>' + keptText +
    '</div>';
  const rows = (tr.detections || []).map(d =>
    '<tr><td>' + esc(d.entity_type) + '</td><td>' + esc(d.source) + '</td><td>' + esc(d.strategy) + '</td>' +
    '<td><code>' + esc(d.original) + '</code></td><td class="arrow">→</td>' +
    '<td><code>' + esc(d.strategy === 'keep' ? '（保留原样）' : (d.replacement || '（删除）')) + '</code></td>' +
    '<td>' + esc(locText(d.locator)) + '</td></tr>'
  ).join('');
  const table = (tr.detections || []).length
    ? '<table><tr><th>类型</th><th>来源</th><th>策略</th><th>原文</th><th></th><th>替换为</th><th>位置</th></tr>' + rows + '</table>'
    : '<div class="meta">本次未命中任何敏感信息。</div>';
  $('logBody').innerHTML = meta + table;
}

function locText(loc) {
  if (!loc) return '';
  if ('line' in loc) return '第' + (loc.line + 1) + '行';
  if ('page' in loc) return '第' + (loc.page + 1) + '页' + (loc.bbox ? '(图)' : '');
  if ('sheet' in loc) return loc.sheet + '!' + loc.cell;
  if ('row' in loc) return 'r' + loc.row + 'c' + loc.col;
  if ('paragraph' in loc) return '第' + (loc.paragraph + 1) + '段';
  return JSON.stringify(loc);
}

function renderStats(counts) {
  const entries = Object.entries(counts || {});
  $('statsCard').classList.remove('hidden');
  $('stats').innerHTML = '<tr><th>类型</th><th>数量</th></tr>' +
    (entries.length ? entries.map(([k, v]) => '<tr><td>' + k + '</td><td>' + v + '</td></tr>').join('')
      : '<tr><td colspan="2" style="color:var(--muted)">未命中</td></tr>');
}
function showErr(msg) { const e = $('err'); e.textContent = msg; e.classList.remove('hidden'); }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

loadPresets();
loadConfigs();
