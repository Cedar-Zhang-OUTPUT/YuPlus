// This entry only invokes the installed Yu+ Skill. MCP belongs to the Agent client.
export const EAGLE_CONNECT_PROMPT = '使用 $yuplus 连接 Eagle 案例库。';

export function eagleLibraryEntry({copy = text => navigator.clipboard.writeText(text)} = {}) {
  const el = (tag, cls, text = '') => {
    const node = document.createElement(tag); node.className = cls; node.textContent = text; return node;
  };
  const panel = el('section', 'eagle-library-entry');
  panel.setAttribute('aria-label', 'Eagle 本地案例库');
  const body = el('div', 'eagle-library-body');
  body.append(el('h2', '', 'Eagle 本地案例库'),
    el('p', '', '让 Agent 从你收藏的图片与文件中查找案例。素材保留在 Eagle，检索默认只读。'),
    el('p', 'muted', '复制连接指令到 Codex，按引导完成配置与验证；使用时保持 Eagle 和官方 MCP 插件运行。'));
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
  prompt.readOnly = true; prompt.rows = 2; prompt.value = EAGLE_CONNECT_PROMPT;
  fallback.append(label, prompt);
  button.onclick = async () => {
    if (button.disabled) return;
    button.disabled = true; status.textContent = '正在复制连接指令…';
    try {
      await copy(EAGLE_CONNECT_PROMPT);
      fallback.hidden = true;
      status.textContent = '已复制。粘贴到 Codex 后开始连接，连接结果和资源库名称会在对话中确认。';
    } catch {
      fallback.hidden = false;
      status.textContent = '未能自动复制，请复制下方指令，发送到 Codex。';
      prompt.focus(); prompt.select();
    } finally { button.disabled = false; }
  };
  panel.append(body, actions, status, fallback);
  return panel;
}
