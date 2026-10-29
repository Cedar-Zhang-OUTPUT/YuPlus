// Workspace source preferences; project content remains read-only.
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

export async function saveLibraryRequest(request, fetcher = fetch) {
  const response = await fetcher('/api/libraries', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(request),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error?.message || '保存失败，请稍后重试。');
  return result.libraries;
}

export function libraryLogo(library) {
  if (typeof library.logo === 'string' && /^\/assets\/library-logos\/[a-z0-9-]+\.png$/.test(library.logo)) return library.logo;
  if (library.kind === 'feishu_folder') return '/assets/library-logos/feishu-cn.png';
  const url = websiteUrl(library.url);
  return url ? new URL(url).origin + '/favicon.ico' : null;
}

export function libraryView(libraries, state, {save = saveLibraryRequest, onChange = () => {}, demo = false} = {}) {
  const el = (tag, cls = '', text = '') => {
    const node = document.createElement(tag); node.className = cls;
    node.textContent = text; return node;
  };
  let records = libraries || [];
  state.tab ||= 'official';
  const page = el('div', 'content library-catalog');
  const header = el('div', 'library-heading');
  const intro = el('div', 'library-intro');
  intro.append(el('p', 'muted', '连接灵感来源，让每一次案例研究都有迹可循。'));
  const summary = el('p', 'library-summary'); intro.append(summary);
  const tools = el('div', 'library-tools');
  const search = el('input', 'library-search'); search.type = 'search';
  search.placeholder = '搜索案例库源'; search.value = state.search || '';
  search.setAttribute('aria-label', '搜索案例库源');
  const add = el('button', 'library-primary', '＋ 添加源'); add.type = 'button';
  add.setAttribute('aria-expanded', String(!!state.addOpen)); add.setAttribute('aria-controls', 'library-add-form');
  tools.append(search, add); header.append(intro, tools); page.append(header);
  const tabs = el('div', 'library-tabs'); tabs.setAttribute('aria-label', '来源分类');
  const tabButtons = {};
  for (const [key, label] of [['official', 'Official'], ['personal', 'Personal']]) {
    const button = el('button', '', label); button.type = 'button';
    button.onclick = () => { state.tab = key; draw(); };
    tabButtons[key] = button; tabs.append(button);
  }
  const notice = el('p', 'library-notice'); notice.setAttribute('role', 'status'); notice.setAttribute('aria-live', 'polite');
  const list = el('div', 'library-sections');
  const form = el('form', 'library-add-form'); form.id = 'library-add-form'; form.hidden = !state.addOpen;
  form.append(el('h2', '', '添加 Personal 源'), el('p', 'muted', '保存你常用的网站或飞书共享文件夹，添加后默认启用。'));
  const fields = {};
  for (const [key, label, tag] of [['kind', '来源类型', 'select'], ['name', '名称', 'input'], ['url', '链接', 'input']]) {
    const field = el('div', 'library-field'); const caption = el('label', '', label); caption.htmlFor = 'library-' + key;
    const input = el(tag); input.id = caption.htmlFor; input.required = true;
    if (key === 'kind') {
      for (const [value, text] of [['website', '网站'], ['feishu_folder', '飞书共享文件夹']]) {
        const option = el('option', '', text); option.value = value; input.append(option);
      }
      input.value = state.kind || 'website';
    } else {
      input.type = key === 'url' ? 'url' : 'text'; input.maxLength = key === 'url' ? 4096 : 200;
      input.value = state[key] || ''; input.placeholder = key === 'url' ? 'https://…' : '为这个来源命名';
    }
    input.oninput = () => { state[key] = input.value; validate(); };
    input.onchange = input.oninput;
    fields[key] = input; field.append(caption, input); form.append(field);
  }
  const formError = el('p', 'library-form-error'); formError.id = 'library-form-error'; formError.setAttribute('aria-live', 'polite');
  fields.url.setAttribute('aria-describedby', formError.id);
  const actions = el('div', 'library-form-actions');
  const submit = el('button', 'library-primary', '添加并启用'); submit.type = 'submit';
  const cancel = el('button', 'chipbtn', '取消'); cancel.type = 'button';
  const showForm = (open) => { state.addOpen = open; form.hidden = !open; add.setAttribute('aria-expanded', String(open)); };
  add.onclick = () => { showForm(!state.addOpen); if (state.addOpen) fields.name.focus(); };
  cancel.onclick = () => { showForm(false); add.focus(); };
  actions.append(submit, cancel); form.append(formError, actions);
  page.append(tabs, form, notice, list);
  let pending = false;
  // Retain the same request ID for a failed request so an uncertain write is safe to retry.
  let retry;
  const write = async (action, input, button) => {
    if (pending || demo) return false;
    const fingerprint = JSON.stringify({action, input});
    if (retry?.fingerprint !== fingerprint) retry = {fingerprint, request: {action, input, request_id: 'ui_' + crypto.randomUUID()}};
    pending = true; button.disabled = true; const label = button.textContent; button.textContent = '保存中…';
    notice.textContent = ''; page.setAttribute('aria-busy', 'true');
    try {
      records = await save(retry.request); retry = null; onChange(records);
      notice.textContent = action === 'delete' ? '已移除，此来源不会参与案例研究。' : '已添加，此来源可以用于案例研究。';
      return true;
    } catch (error) {
      notice.textContent = error.message; return false;
    } finally {
      pending = false; button.disabled = false; button.textContent = label; page.setAttribute('aria-busy', 'false'); draw();
    }
  };
  const validate = () => {
    const url = fields.kind.value === 'website' ? websiteUrl(fields.url.value) : folderUrl(fields.url.value);
    const invalid = !!fields.url.value.trim() && !url;
    fields.url.setAttribute('aria-invalid', String(invalid));
    formError.textContent = invalid ? (fields.kind.value === 'website' ? '请输入有效的 http 或 https 网站链接。' : '请输入飞书共享文件夹链接（/drive/folder/…）。') : '';
    submit.disabled = demo || pending || !url || !fields.name.value.trim(); return url;
  };
  form.onsubmit = async (event) => {
    event.preventDefault(); const url = validate(); const name = fields.name.value.trim();
    if (!url || !name || pending || demo) return;
    const existing = records.find(row => row.url === url);
    if (existing && !existing.deleted_at) {
      formError.textContent = '此来源已经启用，可以在列表中搜索查看。'; return;
    }
    const ok = await write(existing ? 'restore' : 'add', existing
      ? {library_id: existing.id, base_version: existing.version}
      : {kind: fields.kind.value, name, url}, submit);
    if (ok) {
      state.tab = existing?.origin || 'personal'; state.search = ''; search.value = '';
      fields.name.value = fields.url.value = ''; state.name = state.url = ''; showForm(false); draw();
      add.focus();
    }
    validate();
  };
  function draw() {
    summary.textContent = `${records.filter(row => !row.deleted_at).length} / ${records.length} 个来源已启用 · 默认全部启用，按需移除`;
    for (const [key, button] of Object.entries(tabButtons)) {
      button.setAttribute('aria-pressed', String(state.tab === key));
      button.textContent = `${key === 'official' ? 'Official' : 'Personal'}  ${records.filter(row => (row.origin || 'personal') === key).length}`;
    }
    list.replaceChildren();
    const query = (state.search || '').trim().toLocaleLowerCase();
    const filtered = records.filter(row => (row.origin || 'personal') === state.tab &&
      `${row.name} ${row.url} ${row.description || ''}`.toLocaleLowerCase().includes(query));
    if (!filtered.length) {
      const empty = el('div', 'library-empty');
      empty.append(el('h2', '', query ? '没有匹配的来源' : '收藏你的灵感来源'), el('p', 'muted', query ? '试试其他名称或网址。' : '点击“添加源”，把常用网站和飞书文件夹放在这里。'));
      list.append(empty);
    }
    const groups = new Map();
    for (const row of filtered) {
      const group = state.tab === 'personal' ? '我的来源' : row.category || '内置来源';
      if (!groups.has(group)) groups.set(group, []); groups.get(group).push(row);
    }
    for (const [name, rows] of groups) {
      const section = el('section', 'library-section'); section.append(el('h2', '', name));
      const grid = el('div', 'library-source-grid');
      for (const row of rows.sort((a, b) => a.name.localeCompare(b.name))) {
        const item = el('article', 'library-source');
        const icon = el('span', 'library-source-icon');
        icon.setAttribute('aria-hidden', 'true');
        const fallback = el('span', '', row.name.slice(0, 2).toUpperCase()); icon.append(fallback);
        const logo = libraryLogo(row);
        if (logo) {
          const img = el('img', 'library-logo'); img.alt = ''; img.width = img.height = 32;
          img.referrerPolicy = 'no-referrer'; img.decoding = 'async'; img.hidden = true;
          img.onload = () => { img.hidden = false; fallback.hidden = true; };
          img.onerror = () => { img.hidden = true; fallback.hidden = false; };
          img.src = logo; icon.append(img);
        }
        const body = el('div', 'library-source-body'); const title = el('h3');
        const url = row.kind === 'website' ? websiteUrl(row.url) : folderUrl(row.url);
        if (url) {
          const link = el('a', '', row.name); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; title.append(link);
        } else title.textContent = row.name;
        const description = row.description || (row.kind === 'feishu_folder' ? '飞书共享文件夹' : url ? new URL(url).hostname : '链接不可用');
        body.append(title, el('p', 'muted', description), el('span', 'library-source-status', row.deleted_at ? '未启用' : '已启用'));
        const toggle = el('button', 'library-toggle', row.deleted_at ? '＋ 添加' : '− 移除'); toggle.type = 'button';
        toggle.disabled = demo || pending;
        toggle.setAttribute('aria-label', `${row.deleted_at ? '添加' : '移除'} ${row.name}`);
        toggle.onclick = async () => {
          await write(row.deleted_at ? 'restore' : 'delete', {library_id: row.id, base_version: row.version}, toggle);
          list.querySelector(`[data-library-id="${CSS.escape(row.id)}"]`)?.focus();
        };
        toggle.dataset.libraryId = row.id;
        item.append(icon, body, toggle); grid.append(item);
      }
      section.append(grid); list.append(section);
    }
  }
  search.oninput = () => { state.search = search.value; draw(); };
  if (demo) notice.textContent = '模拟预览：请在本地工作空间中添加或移除来源。';
  validate(); draw(); return page;
}
