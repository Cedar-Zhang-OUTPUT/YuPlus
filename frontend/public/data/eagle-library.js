// MCP belongs to the Agent client; the page displays its saved observations.
export const EAGLE_CONNECT_PROMPT = '使用 $yuplus 连接 Eagle 案例库。';

export async function loadEagleStatus(signal) {
  const response = await fetch('/api/eagle', {cache:'no-store', signal});
  if (!response.ok) throw new Error('status unavailable');
  const result = await response.json();
  if (!result.ok || !result.data || !Number.isInteger(result.data.version)) throw new Error('invalid status');
  return result.data;
}

export function eagleStatusText(record, now = Date.now()) {
  const state = record?.state || 'not_configured';
  const connected = ['connected', 'verified'].includes(state);
  const stamp = Date.parse(record?.observed_at);
  const stale = connected && (!Number.isFinite(stamp) || now - stamp > 24 * 60 * 60 * 1000);
  const labels = {not_configured:'尚未记录连接', configured:'配置已写入', waiting:'等待客户端加载',
    connected:'已连接 · 素材待验证', verified:'已连接 · 读取已验证', unavailable:'连接不可用'};
  return {label: stale ? '连接待复核' : labels[state] || '状态待确认', connected, stale,
    detail: [record?.library_name && `资源库：${record.library_name}`,
      ({metadata:'元数据可读', thumbnail:'缩略图可读', original:'原文件可读'})[record?.material_read],
      Number.isFinite(stamp) && `最近检查：${new Date(stamp).toLocaleString('zh-CN', {hour12:false})}`].filter(Boolean).join(' · ')};
}

// Sequential polling with cancellation; no background loop survives leaving the page.
export function watchEagleStatus({load = loadEagleStatus, update, failed, visible = () => !document.hidden,
  schedule = (fn, ms) => setTimeout(fn, ms), cancel = clearTimeout}) {
  let stopped = false, timer, controller;
  async function tick() {
    if (stopped) return;
    if (visible()) {
      controller = new AbortController();
      try { const record = await load(controller.signal); if (!stopped) update(record); }
      catch { if (!stopped) failed(); }
    }
    if (!stopped) timer = schedule(tick, 5000);
  }
  tick();
  return () => { stopped = true; cancel(timer); controller?.abort(); };
}

export function eagleLibraryEntry({copy = text => navigator.clipboard.writeText(text), record,
  dataDir, load = loadEagleStatus} = {}) {
  const el = (tag, cls, text = '') => {
    const node = document.createElement(tag); node.className = cls; node.textContent = text; return node;
  };
  const panel = el('section', 'eagle-library-entry');
  panel.setAttribute('aria-label', 'Eagle 本地案例库');
  const body = el('div', 'eagle-library-body');
  const heading = el('div', 'eagle-library-heading');
  const badge = el('span', 'eagle-library-badge');
  heading.append(el('h2', '', 'Eagle 本地案例库'), badge);
  body.append(heading,
    el('p', '', '让 Agent 从你收藏的图片与文件中查找案例。素材保留在 Eagle，检索默认只读。'),
    el('p', 'muted', '复制连接指令到 Codex，按引导完成配置与验证；使用时保持 Eagle 和官方 MCP 插件运行。'));
  const details = el('p', 'eagle-library-details');
  const note = el('p', 'muted');
  const observation = el('div', 'eagle-library-observation');
  observation.setAttribute('role', 'status'); observation.setAttribute('aria-live', 'polite'); observation.setAttribute('aria-atomic', 'true');
  const announcement = el('span', 'eagle-library-sr');
  observation.append(announcement, details, note); body.append(observation);
  const actions = el('div', 'eagle-library-actions');
  const button = el('button', 'library-primary', '连接 Eagle 案例库'); button.type = 'button';
  const plugin = el('a', '', '官方 MCP 插件');
  plugin.href = 'https://community-cn.eagle.cool/plugin/mcp-server';
  plugin.target = '_blank'; plugin.rel = 'noopener noreferrer';
  actions.append(button, plugin);
  const status = el('p', 'eagle-library-status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const fallback = el('div', 'eagle-library-fallback'); fallback.hidden = true;
  const label = el('label', '', '连接指令'); label.htmlFor = 'eagle-connect-prompt';
  const prompt = el('textarea', ''); prompt.id = label.htmlFor;
  const connectPrompt = dataDir ? `${EAGLE_CONNECT_PROMPT} Yu+ 数据目录：${JSON.stringify(dataDir)}。验证后将结果回写此工作空间。` : EAGLE_CONNECT_PROMPT;
  prompt.readOnly = true; prompt.rows = 2; prompt.value = connectPrompt;
  fallback.append(label, prompt);
  button.onclick = async () => {
    if (button.disabled) return;
    button.disabled = true; status.textContent = '正在复制连接指令…';
    try {
      await copy(connectPrompt);
      fallback.hidden = true;
      status.textContent = '已复制。粘贴到 Codex 后验证连接，结果会自动更新到这里。';
    } catch {
      fallback.hidden = false;
      status.textContent = '未能自动复制，请复制下方指令，发送到 Codex。';
      prompt.focus(); prompt.select();
    } finally { button.disabled = false; }
  };
  let current = record, lastDisplay;
  // Avoid repeating live-region announcements when the observation is unchanged.
  const update = value => {
    current = value;
    const display = eagleStatusText(value);
    const signature = JSON.stringify([value, display.label]);
    if (signature === lastDisplay) return;
    lastDisplay = signature;
    badge.textContent = display.label; announcement.textContent = display.label + '。';
    badge.className = 'eagle-library-badge' + (display.connected && !display.stale ? ' is-connected' : '');
    details.textContent = display.detail;
    note.textContent = value?.observed_at ? '以上为 Agent 最近检查结果，不代表实时在线状态；切换资源库后请重新验证。' : '连接过的库也需要由 Agent 验证并同步一次，才会在这里显示。';
    button.textContent = value?.version ? '重新验证连接' : '连接 Eagle 案例库';
  };
  update(record);
  let stop;
  panel.start = () => { stop?.(); stop = watchEagleStatus({load, update,
    failed: () => { lastDisplay = undefined; update(current); lastDisplay = undefined; badge.textContent = '状态暂时无法更新'; announcement.textContent = '状态暂时无法更新。'; badge.className = 'eagle-library-badge'; note.textContent = '未能读取最新记录；已显示的内容为上次结果，请确认 Yu+ 服务仍在运行。'; }}); };
  panel.destroy = () => { stop?.(); stop = null; };
  panel.append(body, actions, status, fallback);
  return panel;
}
