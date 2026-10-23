import {createPreviewController,previewTransport} from './case-preview.js';

export function secondTime(value) {
  const date=new Date(value);if(!value || !Number.isFinite(date.getTime())) return '—';
  const p=n=>String(n).padStart(2,'0');
  return `${date.getFullYear()}-${p(date.getMonth()+1)}-${p(date.getDate())} ${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
}
export function caseVersions(data,projectId) {
  return (data.case_findings||[]).filter(r=>r.project_id===projectId && typeof r.id==='string' && Number.isInteger(r.version) && r.version>0).slice().sort((a,b)=>b.version-a.version);
}
export function caseFindingPrompt(project,data) {
  return `请为 Yu+ 项目「${project.name}」（project_id：${project.id}）开启一轮新的找案例研究，按 Yu+ Skill 新建研究版本，不要覆盖或续改已有研究。`+
    (data.meta?.demo?'\n这是界面示例，请先指定真实项目。':`\n数据目录：${JSON.stringify(data.meta.data_dir)}`);
}
export function originalUrl(value) {
  try { const url=new URL(value);return url.protocol==='https:' && !url.username && !url.password && /(^|\.)(feishu\.cn|larksuite\.com)$/.test(url.hostname)?url.href:null; } catch {return null;}
}
export function setBoardLink(link,record) {
  const url=originalUrl(record?.board_url)||originalUrl(record?.document_url);
  link.target='_blank';link.rel='noopener noreferrer';
  link.setAttribute('aria-disabled',String(!url));
  link.title=url?'在新标签页打开当前版本的飞书画板':'当前版本尚未提供飞书画板链接';
  if(url)link.href=url;else link.removeAttribute('href');
  return url;
}
const el=(tag,cls,text)=>{const node=document.createElement(tag);node.className=cls||'';if(text) node.textContent=text;return node;};
const button=(text,label,action)=>{const node=el('button','chipbtn',text);node.type='button';node.setAttribute('aria-label',label);node.title=label;node.onclick=action;return node;};

export function caseFindingView(data,project,state,copy) {
  const versions=caseVersions(data,project.id);
  const page=el('div','content wide case-finding-page');
  const heading=el('div','case-heading');heading.append(el('h1','largetitle','找案例'));
  const trigger=button('暂无版本','找案例历史版本',()=>{
    if(menu.matches(':popover-open')){menu.hidePopover();return;}
    const rect=trigger.getBoundingClientRect();menu.style.left=Math.max(12,Math.min(rect.left,innerWidth-324))+'px';menu.style.top=(rect.bottom+8)+'px';
    menu.showPopover();options.find(n=>n.getAttribute('aria-checked')==='true')?.focus();
  });
  trigger.classList.add('version-trigger');trigger.disabled=!versions.length;trigger.setAttribute('aria-haspopup','menu');trigger.setAttribute('aria-expanded','false');trigger.setAttribute('aria-controls','caseVersions');
  const menu=el('div','version-menu case-version-menu');menu.id='caseVersions';menu.setAttribute('popover','auto');menu.setAttribute('role','menu');menu.setAttribute('aria-label','找案例历史版本');
  const options=[];
  menu.addEventListener('toggle',()=>trigger.setAttribute('aria-expanded',String(menu.matches(':popover-open'))));
  menu.onkeydown=e=>{
    const i=options.indexOf(document.activeElement);
    if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();options[e.key==='Home'?0:e.key==='End'?options.length-1:(i+(e.key==='ArrowDown'?1:-1)+options.length)%options.length]?.focus();}
    if(['Escape','Tab'].includes(e.key)){menu.hidePopover();trigger.focus();if(e.key==='Escape')e.preventDefault();}
  };
  trigger.onkeydown=e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();trigger.click();}};
  heading.append(trigger,menu);if(data.meta?.demo) heading.append(el('span','tag case-demo-label','示例画板'));
  page.append(heading);

  const board=el('section','card case-board');board.setAttribute('aria-label','案例画板预览');
  const tools=el('div','case-board-tools');
  const status=el('span','small muted case-board-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const original=el('a','chipbtn','打开飞书画板 ↗');original.setAttribute('aria-label','在新标签页打开当前版本飞书画板');setBoardLink(original,null);
  const refresh=button('↻','刷新画板预览',()=>controller.refresh());
  tools.append(status,original,refresh);
  const viewport=el('div','case-board-viewport');viewport.tabIndex=0;viewport.setAttribute('aria-label','画板，使用缩放按钮放大，方向键平移');
  const image=el('img','case-board-image');image.alt='案例画板图片预览';image.draggable=false;image.hidden=true;
  const empty=el('div','case-board-empty');
  const glyph=el('div','case-board-glyph','◇');glyph.setAttribute('aria-hidden','true');
  const emptyTitle=el('h3','','还没有案例画板');const emptyNote=el('p','small muted','从下方复制提示词，开始找案例。');empty.append(glyph,emptyTitle,emptyNote);
  viewport.append(image,empty);
  let zoom=1,x=0,y=0,dimensions=null,drag=null,selected=null,lastImage=null,fullscreen=false;
  const zoomLabel=el('span','case-zoom-label','100%');
  const controls=el('div','case-board-controls');
  function transform(){
    if(!dimensions)return;
    const fit=Math.min((viewport.clientWidth-48)/dimensions.width,(viewport.clientHeight-48)/dimensions.height);
    const width=Math.max(1,dimensions.width*fit*zoom),height=Math.max(1,dimensions.height*fit*zoom);
    x=Math.max(-width/2,Math.min(width/2,x));y=Math.max(-height/2,Math.min(height/2,y));
    image.style.width=width+'px';image.style.height=height+'px';image.style.transform=`translate(calc(-50% + ${x}px),calc(-50% + ${y}px))`;
    zoomLabel.textContent=Math.round(zoom*100)+'%';
  }
  const zoomTo=value=>{zoom=Math.max(.5,Math.min(4,value));transform();};
  const less=button('−','缩小画板',()=>zoomTo(zoom/1.25));const more=button('+','放大画板',()=>zoomTo(zoom*1.25));
  const fit=button('适应','适应画板大小',()=>{zoom=1;x=y=0;transform();});
  const dialog=el('dialog','case-board-dialog');dialog.setAttribute('aria-label','案例画板放大预览');
  const expand=button('⛶','展开画板',()=>{
    if(fullscreen){dialog.close();return;}
    fullscreen=true;board.classList.add('is-expanded');dialog.append(board);page.append(dialog);dialog.showModal();
    expand.setAttribute('aria-expanded','true');expand.setAttribute('aria-label','收起画板');expand.title='收起画板';transform();
  });
  dialog.addEventListener('close',()=>{
    fullscreen=false;board.classList.remove('is-expanded');page.insertBefore(board,dock);dialog.remove();
    expand.setAttribute('aria-expanded','false');expand.setAttribute('aria-label','展开画板');expand.title='展开画板';transform();expand.focus();
  });
  expand.setAttribute('aria-expanded','false');controls.append(less,zoomLabel,more,fit,expand);
  viewport.onpointerdown=e=>{if(!dimensions || e.button!==0)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY};viewport.setPointerCapture(e.pointerId);viewport.classList.add('is-dragging');};
  viewport.onpointermove=e=>{if(!drag || e.pointerId!==drag.id)return;x+=e.clientX-drag.x;y+=e.clientY-drag.y;drag={...drag,x:e.clientX,y:e.clientY};transform();};
  const release=()=>{drag=null;viewport.classList.remove('is-dragging');};viewport.onpointerup=release;viewport.onpointercancel=release;viewport.onlostpointercapture=release;
  viewport.onkeydown=e=>{
    if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','-','0'].includes(e.key)){e.preventDefault();if(e.key==='ArrowLeft')x+=40;if(e.key==='ArrowRight')x-=40;if(e.key==='ArrowUp')y+=40;if(e.key==='ArrowDown')y-=40;if(e.key==='+')zoomTo(zoom*1.25);if(e.key==='-')zoomTo(zoom/1.25);if(e.key==='0'){zoom=1;x=y=0;}transform();}
  };
  const escape=e=>{if(e.key==='Escape' && fullscreen){expand.click();expand.focus();}};document.addEventListener('keydown',escape);
  board.append(tools,viewport,controls);page.append(board);

  const dock=el('section','card case-finding-dock');dock.setAttribute('aria-label','找案例提示词');
  const header=el('header');header.append(el('h3','grow','找案例'),el('span','tag library-tag-blue','在 Codex 中开始'));
  const body=el('div','body'),box=el('div','copyable project-prompt-box');
  box.append(el('span','grow','开启一轮新的案例研究，保留已有版本。'));
  const copyButton=button('复制找案例 Prompt','复制找案例提示词',()=>copy(caseFindingPrompt(project,data),copyButton));box.append(copyButton);body.append(box);dock.append(header,body);page.append(dock);

  const fetchPreview=previewTransport(data,project.id);
  const controller=createPreviewController({fetchPreview,demo:data.meta?.demo===true,onState:result=>{
    const {snapshot,phase}=result;refresh.disabled=!selected || !fetchPreview || phase==='loading';
    less.disabled=more.disabled=fit.disabled=!snapshot;
    if(snapshot){
      if(lastImage!==snapshot.image_url){image.src=snapshot.image_url;lastImage=snapshot.image_url;}
      dimensions=snapshot;image.hidden=false;empty.hidden=true;transform();
    } else {image.hidden=true;empty.hidden=false;dimensions=null;lastImage=null;}
    if(!selected){status.textContent='';emptyTitle.textContent='还没有案例画板';emptyNote.textContent='从下方复制提示词，开始找案例。';}
    else {
      emptyTitle.textContent=phase==='unbound'?'本轮画板尚未关联':phase==='loading'?'正在获取画板预览':phase==='blocked'?'需要处理飞书访问权限':'暂时没有可用预览';
      emptyNote.textContent=phase==='unbound'?'Agent 保存飞书画板后，刷新页面即可查看。':phase==='loading'?'首次获取可能需要一些时间。':phase==='blocked'?'恢复登录或权限后，点击刷新重试。':phase==='unavailable'?'画板预览服务尚未接入。':'可点击刷新重试，或打开飞书原画板。';
      const time=snapshot?`最近获取 ${secondTime(snapshot.fetched_at)}`:'';
      const hint=phase==='loading'?'正在刷新…':phase==='blocked'?result.message:phase==='error'?result.message:phase==='unavailable'?'预览服务待接入':'';
      status.textContent=[time,hint].filter(Boolean).join(' · ');
    }
  }});
  function select(record){
    selected=record;state.versionId=record?.id;zoom=1;x=y=0;lastImage=null;dimensions=null;image.hidden=true;
    trigger.textContent=record?`v${record.version}　⌄`:'暂无版本';
    for(let i=0;i<options.length;i++)options[i].setAttribute('aria-checked',String(versions[i].id===record?.id));
    setBoardLink(original,record);
    controller.select(record);
  }
  for(const version of versions){
    const option=button('',`查看 v${version.version}`,()=>{menu.hidePopover();select(version);trigger.focus();});option.className='btn version-option';option.setAttribute('role','menuitemradio');option.tabIndex=-1;
    const label=el('span');label.append(el('b','',`v${version.version}`),el('small','',`创建于 ${secondTime(version.created_at)}`),el('small','',`更新于 ${secondTime(version.updated_at)}`));option.append(label);menu.append(option);options.push(option);
  }
  const observer=new ResizeObserver(transform);observer.observe(viewport);
  let onScreen=true;
  const visibility=()=>controller.setVisible(!document.hidden && onScreen);
  const intersection=new IntersectionObserver(entries=>{onScreen=entries[0].isIntersecting;visibility();});intersection.observe(board);
  document.addEventListener('visibilitychange',visibility);visibility();
  select(versions.find(r=>r.id===state.versionId)||versions[0]||null);
  return {element:page,destroy(){controller.destroy();observer.disconnect();intersection.disconnect();if(dialog.open)dialog.close();document.removeEventListener('visibilitychange',visibility);document.removeEventListener('keydown',escape);}};
}
