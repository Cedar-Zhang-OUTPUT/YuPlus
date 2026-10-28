// This page only reads registered sources and prepares a clipboard request.
export function folderUrl(value) {
  if (typeof value !== 'string' || value.length > 4096 || /[\x00-\x1f]/.test(value)) return null;
  const text = value.trim();
  if (!/^https:\/\//i.test(text) || text.includes('\\')) return null;
  try {
    const url = new URL(text);
    const validHost = ['feishu.cn', 'larksuite.com'].some(d => url.hostname === d || url.hostname.endsWith('.' + d));
    const path = url.pathname.match(/^\/(?:drive\/)?folder\/([A-Za-z0-9_-]+)\/*$/);
    if (!validHost || url.username || url.password || url.port || !path) return null;
    return `https://${url.hostname}/drive/folder/${path[1]}`;
  } catch { return null; }
}

export function websiteUrl(value) {
  if (typeof value !== 'string' || value.length > 4096 || /[\x00-\x1f]/.test(value) || value.includes('\\')) return null;
  if (!/^https?:\/\//i.test(value.trim()) || value.trim().split('/')[2].includes('@')) return null;
  try {
    const url = new URL(value.trim());
    if (!url.hostname || url.username || url.password || /\s|%/.test(url.hostname)) return null;
    return url.href;
  } catch { return null; }
}

export function libraryPrompt(value, kind = 'feishu_folder') {
  if (kind === 'website') {
    const url = websiteUrl(value);
    return url ? `请用 Yu+ 将这个网站添加为工作空间的案例库源：${url}。读取网站名称，以 kind=website 保存名称和链接，并告诉我 library_id；若已存在则使用已有记录。本次只登记案例库源，不保存网站内容；需要案例时再通过浏览器或网页搜索到这个网站中查找。` : null;
  }
  if (kind !== 'feishu_folder') return null;
  const url = folderUrl(value);
  return url ? `请用 Yu+ 将这个飞书共享文件夹添加为工作空间的案例库源：${url}。读取文件夹名称，以 kind=feishu_folder 保存名称和链接，并告诉我 library_id；若已存在则使用已有记录。本次只登记案例库源，不保存文件夹内容；使用时再通过飞书 CLI 到文件夹中查找。` : null;
}

export function libraryRemovalPrompt(library) {
  return `请用 Yu+ 移除案例库登记 ${JSON.stringify(library.name)}（library_id：${library.id}）。先读取当前记录核对身份和版本，再执行 library delete；仅移除 Yu+ 中的登记，不删除${library.kind === 'website' ? '网站或网站内容' : '飞书文件夹或里面的内容'}。`;
}

export function libraryView(libraries, state, copy, fullTime) {
  const el = (tag, cls, text) => {
    const node = document.createElement(tag); node.className = cls;
    if (text) node.textContent = text;
    return node;
  };
  const page = el('div', 'content wide projects-content');
  page.append(el('p', 'muted', '保存可供项目参考的飞书共享文件夹和网站，所有项目共用。'));
  const grid = el('div', 'library-grid');
  const records = (libraries || []).filter(row => !row.deleted_at);
  for (const library of records) {
    const card = el('article', 'card library-card');
    const header = el('header');
    const title = el('h3', 'grow');
    const website = library.kind === 'website';
    const url = website ? websiteUrl(library.url) : folderUrl(library.url);
    if (url) {
      const link = el('a', 'library-link', library.name);
      link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', `${library.name}（在新标签页打开${website ? '网站' : '飞书文件夹'}）`);
      title.append(link);
    } else title.textContent = library.name;
    header.append(title, el('span', 'tag library-tag-gray', website ? '网站' : '飞书共享文件夹'));
    const body = el('div', 'body');
    if (!url) body.append(el('p', 'small muted', '链接不可用，请让 Agent 检查这条案例库记录。'));
    body.append(el('p', 'tiny muted', `保存于 ${fullTime(library.created_at)}`));
    const remove = el('button', 'chipbtn library-remove', '复制移除指令');
    remove.type = 'button';
    remove.setAttribute('aria-label', `复制移除案例库 ${library.name} 的提示词`);
    remove.onclick = () => copy(libraryRemovalPrompt(library), remove);
    body.append(remove);
    card.append(header, body); grid.append(card);
  }
  if (!records.length) {
    const card = el('section', 'card'); const body = el('div', 'body');
    body.append(el('h3', '', '还没有案例库'), el('p', 'small muted', '填写下方的飞书共享文件夹或网站链接，复制对应提示词交给 Agent 添加。'));
    card.append(body); page.append(card);
  } else page.append(grid);

  const dock = el('section', 'card project-create-dock'); dock.setAttribute('aria-label', '新增案例库');
  const header = el('header'); header.append(el('h3', 'grow', '新增案例库'), el('span', 'tag library-tag-blue', '在 Codex 中添加'));
  const body = el('div', 'body');
  for (const [kind, key, id, title, placeholder] of [
    ['feishu_folder', 'url', 'library-url', '飞书共享文件夹', '粘贴飞书共享文件夹链接'],
    ['website', 'websiteUrl', 'library-website-url', '网站', '粘贴网站链接，如 https://example.com']
  ]) {
    const row = el('div', 'library-create-row');
    const label = el('label', 'small', `${title}链接（必填）`); label.htmlFor = id;
    const box = el('div', 'copyable library-prompt-box');
    const input = el('input', 'project-prompt-input library-url');
    input.id = id; input.type = 'url'; input.required = true; input.autocomplete = 'off';
    input.placeholder = placeholder; input.value = state[key] || '';
    input.setAttribute('aria-describedby', id + '-help');
    const button = el('button', 'chipbtn', `复制新增${title}指令`); button.type = 'button';
    const hint = el('p', 'small muted'); hint.id = id + '-help'; hint.setAttribute('aria-live', 'polite');
    const update = () => {
      state[key] = input.value;
      const valid = !!libraryPrompt(input.value, kind);
      button.disabled = !valid;
      input.setAttribute('aria-invalid', String(!!input.value.trim() && !valid));
      hint.textContent = !input.value.trim() ? `填写${title}链接后即可复制。` : valid
        ? '复制后发给 Agent，保存完成后刷新即可查看。'
        : kind === 'website' ? '请填写有效的 http 或 https 网站链接，不支持含登录凭据的链接。'
          : '请填写 https 飞书共享文件夹链接（/drive/folder/…），不支持文档或群聊链接。';
    };
    input.oninput = update; input.onchange = update;
    button.onclick = () => { update(); const prompt = libraryPrompt(input.value, kind); if (prompt) copy(prompt, button); };
    update(); box.append(input, button); row.append(label, box, hint); body.append(row);
  }
  dock.append(header, body); page.append(dock);
  return page;
}
