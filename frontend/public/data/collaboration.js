// Read-only saved collaboration state. No inferred Agent progress.
export function collaborationStatus(binding) {
  if (!binding) return {label:'尚未建立协作文档',tone:'gray'};
  if (!binding.enabled) return {label:'同步已暂停',tone:'gray'};
  if (binding.error) return {label:'同步需要关注',tone:'orange'};
  if (binding.conflicts) return {label:`${binding.conflicts} 处变化待确认`,tone:'orange'};
  if (binding.pending) return {label:'飞书有更新待整理',tone:'orange'};
  if (binding.local_pending) return {label:'本地有更新待写回',tone:'orange'};
  return {label:'已同步',tone:'green'};
}
export function collaborationStartPrompt(data, projectId) {
  if (data.meta?.demo) return '当前是 Yu+ 前端模拟数据，请先打开真实项目，再让 Codex 按 Yu+ Skill 进入策划文档场景，整理已有信息并建立飞书协作文档。不要使用示例项目 ID 操作真实数据。';
  const target = JSON.stringify({project_id:projectId, project_name:data.projects?.find(p=>p.id===projectId)?.name, data_dir:data.meta?.data_dir});
  return `请使用 Yu+ Skill，为这个项目进入策划文档场景：${target}。按 references/review-structure.md 和 references/collaboration.md 整理已有信息、生成适用的策划文档，并建立或复用飞书协作文档。保留未确定事项，不编造内容；完成后给我文档链接。`;
}
export function collaborationUpdatePrompt(data, projectId, binding) {
  if (data.meta?.demo) return '当前是 Yu+ 前端模拟数据，请先打开真实项目，再按 Yu+ Skill 将已绑定飞书协作文档的最新内容整理回本地。不要使用示例项目 ID 或链接操作真实数据。';
  const target = JSON.stringify({project_id:projectId, project_name:data.projects?.find(p=>p.id===projectId)?.name,
    data_dir:data.meta?.data_dir, document_url:safeCollaborationUrl(binding?.url)});
  return `请使用 Yu+ Skill，将本项目飞书协作文档的最新内容更新到 Yu+ 本地数据：${target}。按 references/collaboration.md 重新核对绑定并拉取最新修订，处理待整理变化，先改 draft 再更新受影响的 Review，保留来源与历史。本地与飞书内容冲突时先请我确认；本次仅从飞书更新本地，不回写飞书。完成后说明更新结果。`;
}
export function collaborationPanel(binding, {el,tag,formatTime,onStart,onCopyLink,onUpdate}) {
  const card=el('section','card collaboration-card');
  card.setAttribute('aria-label','飞书协作文档');
  const head=el('header');const title=el('b','collaboration-title');title.textContent='飞书协作文档';
  const state=collaborationStatus(binding);head.append(title,tag(state.label,state.tone));card.append(head);
  const body=el('div','body');
  if (!binding) {
    const hint=el('p','muted');hint.textContent='在 Codex 中进入策划文档场景后，将整理已有项目信息并建立飞书协作文档。团队可在其中补充方案和反馈。';body.append(hint);
    const start=el('button','btn primary');start.type='button';start.textContent='复制开始整理指令';
    start.onclick=()=>onStart?.(start);body.append(start);
  } else {
    const actions=el('div','collaboration-actions');
    const url=safeCollaborationUrl(binding.url);
    if (url) {
      const link=el('a','btn primary collaboration-link');link.href=url;link.target='_blank';link.rel='noopener noreferrer';
      link.textContent='打开飞书文档 ↗';actions.append(link);
      const copy=el('button','btn');copy.type='button';copy.textContent='复制飞书链接';
      copy.onclick=()=>onCopyLink?.(url,copy);actions.append(copy);
    }
    const update=el('button','btn');update.type='button';update.textContent='复制更新指令';
    update.title='让 Codex 根据最新飞书文档更新本地项目信息与策划文档';
    update.onclick=()=>onUpdate?.(update);actions.append(update);body.append(actions);
    const meta=el('p','muted');meta.textContent=binding.last_synced_at?`最近同步于 ${formatTime(binding.last_synced_at)}`:'协作文档已绑定，等待首次整理。';body.append(meta);
    if (binding.error) {const note=el('p','collaboration-notice');note.textContent=binding.error.message;body.append(note);}
    if (binding.schedule?.state!=='active') {const note=el('p','muted');note.textContent='自动整理任务尚未启用。程序可检查远端变化，项目内容由 Codex 整理。';body.append(note);}
    if (binding.records?.length) {
      const details=el('details');const summary=el('summary');summary.textContent='查看同步记录';details.append(summary);
      for (const record of binding.records) {
        const row=el('p','collaboration-record');let resolution={};try {resolution=JSON.parse(record.resolution_json||'{}');}catch{}
        const status={pending:'待整理',conflict:'待确认',processed:'已整理'}[record.state]||record.state;
        row.textContent=`${formatTime(record.created_at)} · ${status}${resolution.reason?' · '+resolution.reason:''}`;details.append(row);
      }
      body.append(details);
    }
  }
  card.append(body);return card;
}
export function safeCollaborationUrl(url) {
  try {const u=new URL(url);return u.protocol==='https:'&&!u.username&&!u.password&&['feishu.cn','larksuite.com'].some(d=>u.hostname===d||u.hostname.endsWith('.'+d))&&/^\/docx\/[\w-]+$/.test(u.pathname)?u.href:null;}catch{return null;}
}
