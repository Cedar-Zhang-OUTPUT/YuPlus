// Only copies an Agent instruction. Workspace appearance is written through CLI.
export function logoPrompt(data) {
  if (!data?.meta || data.meta.demo !== false || !data.meta.data_dir) return null;
  return `请按 Yu+ Skill 将我附上的图片压缩后设为左上角头像，保留原图。若尚未附图，请提醒我上传图片。\n数据目录：${JSON.stringify(data.meta.data_dir)}\n这是全局头像设置，不修改项目内容。`;
}

export function initLogoMenu(root, getData, copyText) {
  const trigger = root.querySelector('.logo-trigger');
  const panel = root.querySelector('.logo-menu');
  const copy = root.querySelector('.logo-change');
  const image = trigger.querySelector('img');
  const fallback = trigger.querySelector('.logo-fallback');
  let dismissed = false;
  function open(value) {
    root.classList.toggle('is-open', value);
    trigger.setAttribute('aria-expanded', String(value));
    panel.inert = !value;
    panel.setAttribute('aria-hidden', String(!value));
  }
  root.addEventListener('mouseenter', () => { dismissed = false; open(true); });
  root.addEventListener('mouseleave', () => { if (!root.contains(document.activeElement)) open(false); });
  root.addEventListener('focusin', () => { if (!dismissed) open(true); });
  root.addEventListener('focusout', e => { if (!root.contains(e.relatedTarget)) { open(false); dismissed=false; } });
  trigger.addEventListener('click', () => { dismissed=false; open(true); });
  root.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.stopPropagation(); dismissed=true; open(false); trigger.focus(); }
    if (e.key === 'ArrowDown' && e.target === trigger) { e.preventDefault(); dismissed=false; open(true); copy.focus(); }
  });
  document.addEventListener('pointerdown', e => { if (!root.contains(e.target)) open(false); });
  copy.addEventListener('click', () => {
    const prompt = logoPrompt(getData());
    if (prompt) copyText(prompt, copy);
  });
  image.addEventListener('error', () => { image.hidden=true; fallback.hidden=false; });
  open(false);
  return () => {
    const data=getData(), prompt=logoPrompt(data), url=data?.logo?.url;
    copy.disabled=!prompt;
    copy.title=prompt ? '复制提示词后，在 Codex 中附上图片' : '连接本地 Yu+ 服务后可更改头像';
    if (data?.logo?.custom && /^\/api\/logo\?v=\d+$/.test(url)) {
      if (image.getAttribute('src') !== url) image.src=url;
      image.hidden=false; fallback.hidden=true;
    } else { image.removeAttribute('src'); image.hidden=true; fallback.hidden=false; }
  };
}
