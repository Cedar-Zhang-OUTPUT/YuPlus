'use strict';
// 官网交互演示：模拟 Codex 对话 + 内置浏览器中的 Yu+ 只读页面。
// 全部为预设动画与 Yu+ 自带示例项目「城市记忆展厅」的内容，不连接任何服务。
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const root = $('#codex');
  if (!root) return;

  const log = $('#cxLog'), scroller = $('#cxScroll'), empty = $('#cxEmpty'), suggest = $('#cxSuggest');
  const form = $('#cxForm'), input = $('#cxInput'), skipBtn = $('#cxSkip'), sendBtn = $('#cxSend');
  const stage = $('#yuStage'), insp = $('#yuInsp'), crumb = $('#yuCrumb'), urlBar = $('#brUrl'), saving = $('#yuSaving');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const mobile = () => matchMedia('(max-width: 900px)').matches;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  /* ── 词汇（与 Yu+ 前端一致） ─────────────────────────────── */
  const KIND = {
    statement: ['原文信息', 'var(--blue)'], supplement: ['策划补充', 'var(--green)'], reported: ['转述信息', 'var(--teal)'],
    hypothesis: ['待验证判断', 'var(--orange)'], suggestion: ['建议方向', 'var(--purple)'], decision: ['当前采用', 'var(--indigo)']
  };
  const THEME = code => {
    const n = +code.slice(1);
    if ([1, 2, 3, 11, 13, 14].includes(n)) return 'var(--blue)';
    if ([4, 5, 6, 12].includes(n)) return 'var(--teal)';
    if ([7, 8, 9, 16, 18, 19, 20].includes(n)) return 'var(--orange)';
    return 'var(--purple)';
  };
  const CATALOG = [['D01', 'BD 同步信息'], ['D02', '客户原始 Brief'], ['D03', '招标文件'], ['D04', '场地资料'], ['D05', '甲方客户品牌资料'], ['D06', '受众'],
    ['D07', '总预算区间'], ['D08', '策划预算分配'], ['D09', '时间节点或区间'], ['D10', '客户关键决策节点'], ['D11', '合作类型'], ['D12', '竞争对手分析'],
    ['D13', '客户历史合作方与过往项目'], ['D14', '与甲方的会议纪要'], ['D15', '客户 Q&A 问题表'], ['D17', '主策策略'], ['D18', '交付细节'],
    ['D19', '内外部资源'], ['D20', '职责边界'], ['D21', '项目评级'], ['D22', '风险点'], ['D23', '评审会结论'], ['D24', '开放性问题']];
  const OUTPUTS = [['R01', '主策 Debrief'], ['R02', '项目推进安排'], ['R03', '创意评审记录'], ['R05', '客户 Q&A']];
  const SOURCES = {
    brief: {kind: '飞书', title: '城市记忆展厅｜项目需求与预算说明（V3）', meta: '飞书文档 · 快照 v1 · 6,140 字'},
    oral: {kind: '口述', title: '主策口述：本轮按 60 万推进', meta: '口述 · 你在 Codex 中 · 原话已保存'}
  };

  /* ── 状态 ───────────────────────────────────────────────── */
  let S, tw, runId = 0, fast = reduced, busy = false;
  function reset() {
    runId++; busy = false; fast = reduced;
    S = {sources: [], objects: [], reviews: [], cases: null, history: [], view: 'draft', selDraft: null, selReview: 'R01', inspector: null, flash: null, done: new Set(), clock: 9 * 60 + 38};
    tw = {};
    log.innerHTML = ''; empty.hidden = false; input.value = '';
    root.dataset.pane = 'closed'; setTab('chat');
    renderSuggest(); render(); setBusy(false);
  }
  const CANCEL = Symbol('cancel');
  const guard = id => { if (id !== runId) throw CANCEL; };
  const sleep = ms => new Promise(r => setTimeout(r, fast ? 0 : ms));
  const stamp = (add = 1) => { S.clock += add; const h = Math.floor(S.clock / 60), m = S.clock % 60; return `10-16 ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`; };

  /* ── 打字机：按 key 记录已显示字数，渲染时截断 ───────────────── */
  const tx = (key, full) => `<span data-tw="${key}">${esc(full.slice(0, tw[key] ?? Infinity))}</span>`;
  async function type(id, key, full, speed = 20) {
    if (fast) { tw[key] = Infinity; paint(key, full); return; }
    const step = full.length > 60 ? 2 : 1;
    for (let i = 0; i <= full.length; i += step) {
      guard(id); tw[key] = i; paint(key, full); await sleep(speed);
    }
    tw[key] = Infinity; paint(key, full);
  }
  function paint(key, full) { for (const n of $$(`[data-tw="${CSS.escape(key)}"]`, stage)) n.textContent = full.slice(0, tw[key] ?? Infinity); }

  /* ── 视图 ───────────────────────────────────────────────── */
  const tag = k => `<span class="tag" style="--h:${KIND[k][1]}"><i></i>${KIND[k][0]}</span>`;
  const code = (c, h) => `<span class="code" style="--h:${h || (c[0] === 'R' ? 'var(--indigo)' : THEME(c))}">${c}</span>`;
  const cite = src => `<span class="cite"><span class="pv">${SOURCES[src].kind}</span><span class="tt">${esc(SOURCES[src].title)}</span><span class="ar">↗</span><button type="button" class="vw" data-cite="${src}">查看引用</button></span>`;
  const emptyBox = (glyph, title, text) => `<div class="yu-empty"><div class="eg">${glyph}</div><h3>${title}</h3><p>${text}</p></div>`;
  const TITLES = {projects: '项目', library: '案例库', types: '信息分类说明', draft: '项目信息', review: '策划文档', cases: '案例分析', sources: '原始资料', history: '修改与确认记录'};

  function render() {
    const v = S.view;
    crumb.textContent = TITLES[v];
    for (const b of $$('[data-view]', root)) b.classList.toggle('on', b.dataset.view === v);
    const counts = {draft: S.objects.length, review: S.reviews.length, cases: S.cases ? 'v' + S.cases.version : '', sources: S.sources.length, history: S.history.length};
    for (const e of $$('[data-count]', root)) e.textContent = counts[e.dataset.count] || '';
    const path = {draft: 'draft' + (S.selDraft ? '/obj_' + S.selDraft.toLowerCase() : ''), review: 'review' + (S.reviews.length ? '/obj_' + S.selReview.toLowerCase() : ''), cases: 'cases', sources: 'sources', history: 'history'}[v];
    urlBar.textContent = '127.0.0.1:52817/#/' + (path ? 'p/prj_city/' + path : v === 'projects' ? '' : v);
    stage.innerHTML = `<div class="yu-page">${({projects: vProjects, library: vLibrary, types: vTypes, draft: vDraft, review: vReview, cases: vCases, sources: vSources, history: vHistory})[v]()}</div>`;
    if (v === 'cases' && S.cases) bindBoard();
    renderInspector();
  }

  function vProjects() {
    const rows = [['城市记忆展厅', '市文旅局 · 2027 春季开馆 · 常设展首期策展', '刚刚', true], ['沿江夜游提案', '旅投集团 · 前期咨询 · 尚未收录材料', '10-12'], ['湖畔书展', '出版社联合体 · 已结项并归档', '09-04']];
    return `<h1 class="lt">项目</h1><div class="card list">${rows.map(r => `<button type="button" class="row${r[3] ? ' cur' : ''}" ${r[3] ? 'data-view="draft"' : ''}><span class="pdot"></span><span class="grow"><b>${r[0]}</b><small>${r[1]}</small></span><time>${r[2]}</time></button>`).join('')}</div>
      <p class="hint">新建项目在 Codex 中完成：页面只提供可复制的创建意图，不直接写入。</p>`;
  }
  function vLibrary() {
    return `<h1 class="lt">案例库</h1><div class="card list">
      <div class="row"><span class="code" style="--h:var(--blue)">飞书</span><span class="grow"><b>OUTPUT 案例库</b><small>飞书共享文件夹 · 内容按需查找</small></span></div>
      <div class="row"><span class="code" style="--h:var(--gray)">网站</span><span class="grow"><b>示例参考网站</b><small>参考网站 · 内容按需查找</small></span></div></div>
      <p class="hint">移除与恢复只影响本地登记，不改变飞书文件夹。</p>`;
  }
  function vTypes() {
    return `<h1 class="lt">信息分类说明</h1><p class="sub">了解各类项目信息的用途，按需补充，不必逐项填满。</p><div class="types">${CATALOG.map(([c, n]) => `<div class="ty">${code(c)}<span>${n}</span></div>`).join('')}</div>`;
  }

  function vDraft() {
    if (!S.objects.length) return `<h1 class="lt">项目信息 <button type="button" class="classification-help" data-view="types" aria-label="查看信息分类说明">?</button></h1>${emptyBox('✎', '先放进一份项目资料。', '客户 Brief、会议记录或参考文件都可以。发给 Codex 后，整理需求与条件，并保留原始出处。')}`;
    const obj = S.objects.find(o => o.code === S.selDraft) || S.objects[0];
    const dir = S.objects.map(o => `<button type="button" class="dir${o === obj ? ' on' : ''}" data-obj="${o.code}">${code(o.code)}<span>${o.title}</span><em>${o.items.length}</em></button>`).join('');
    const items = obj.items.map(it => {
      const k = obj.code + '.' + it.id;
      const body = it.fields
        ? `<dl class="fields">${it.fields.map(([a, b], i) => `<dt>${a}</dt><dd${/万元/.test(b) ? ' class="money"' : ''}>${tx(k + '.' + i, b)}</dd>`).join('')}</dl>`
        : `<p class="prose">${tx(k, it.text)}</p>`;
      return `<article class="item${S.flash === k ? ' flash' : ''}" style="--h:${THEME(obj.code)}" data-item="${k}">
        <div class="ih"><b>${it.topic}</b><span class="grow"></span>${tag(it.kind)}</div>${body}
        <div class="isrc"><span class="lbl">依据</span>${cite(it.src)}</div></article>`;
    }).join('');
    return `<h1 class="lt">项目信息 <button type="button" class="classification-help" data-view="types" aria-label="查看信息分类说明">?</button></h1>
      <div class="monitor"><b>项目群更新</b><span class="pill">监控 0 个群</span></div>
      <div class="draft-grid"><nav class="dirlist" aria-label="信息目录">${dir}</nav>
      <section class="card objcard"><header class="oh">${code(obj.code)}<h2>${obj.title}</h2><span class="grow"></span><span class="ver">当前 v${obj.rev}</span><span class="chipbtn">复制引用</span></header>
      <p class="meta">v${obj.rev} · 更新于 ${obj.time}</p><div class="items">${items}</div></section></div>`;
  }

  function vReview() {
    if (!S.reviews.length) return `<h1 class="lt">策划文档</h1>${emptyBox('≣', '可以先整理一版。', '可以继续补充资料，也可以根据已有信息整理策划文档。暂未确定的内容会标出来，方便讨论。')}`;
    const rv = S.reviews.find(r => r.code === S.selReview) || S.reviews[0];
    const list = OUTPUTS.map(([c, n]) => {
      const has = S.reviews.find(r => r.code === c);
      return `<button type="button" class="outp${has ? '' : ' none'}${has === rv ? ' on' : ''}" ${has ? `data-review="${c}"` : 'disabled'}>${code(c, c === 'R05' ? 'var(--teal)' : 'var(--indigo)')}<span>${n}</span><em>${has ? '1 份' : '—'}</em></button>`;
    }).join('');
    const banner = rv.stale ? `<div class="stale"><b>⟳ 依据已变化 · 成果尚未同步</b>：预算信息有变化，Debrief 的预算段落待更新。<div><span class="chipbtn">复制更新指令</span><span class="chipbtn">查看受影响段落</span></div></div>` : '';
    const secs = rv.sections.map(sec => `<h3 class="rh">${sec.h}</h3>${sec.blocks.map(b => {
      const k = rv.code + '.' + b.id;
      if (b.unknown) return `<p class="rp unknown">${tx(k, b.text)}</p>`;
      const deps = b.deps.map(d => `<span class="dep">${code(d[0])}${esc(d[1])}</span>`).join('');
      return `<div class="rblock${S.flash === k ? ' flash' : ''}${b.old ? ' changed' : ''}" data-block="${k}">
        ${b.old ? `<p class="rp old"><del>${esc(b.old)}</del></p>` : ''}<p class="rp">${tx(k, b.text)}</p>
        <div class="ra"><span class="deps">${deps}</span><span class="grow"></span><button type="button" class="chipbtn" data-trace="${k}">完整追溯路径</button><span class="chipbtn">复制引用</span></div></div>`;
    }).join('')}`).join('');
    return `<div class="rtop"><h1 class="lt">策划文档</h1><span class="btn-blue">复制生成飞书文档指令</span></div>
      <div class="review-grid"><nav class="card outs" aria-label="成果"><p class="ch">成果</p>${list}</nav>
      <article class="card doc"><header class="dh">${code(rv.code)}<h2>${rv.title}</h2><small>更新于 ${rv.time}</small><span class="grow"></span><span class="vtag${rv.version > 1 ? ' up' : ''}">v${rv.version}</span></header>
      <div class="db">${banner}${secs}</div></article></div>`;
  }

  function vCases() {
    if (!S.cases) return `<h1 class="lt">案例分析</h1>${emptyBox('◇', '这次想研究什么？', '提供一个项目、一组参考或想探索的方向，分析案例的方法与适用条件，整理成案例参考板。')}`;
    const c = S.cases;
    const cards = c.cards.map((k, i) => `<div class="cc${k.shown ? ' in' : ''}" style="--x:${k.x}px;--y:${k.y}px;--h:${k.h}">
      <div class="art a${i}"></div><p class="cr">参考 · ${k.ref}</p><h4>${k.title}</h4><p>${k.why}</p></div>`).join('');
    return `<div class="rtop"><h1 class="lt">案例分析</h1><span class="vtag">v${c.version}</span><span class="tag" style="--h:var(--gray)"><i></i>示例画板</span></div>
      <section class="card board"><div class="bt"><span class="small">飞书画板 · 可见时每 60 秒自动预览</span><span class="grow"></span>
        <button type="button" class="chipbtn" data-zoom="-1" aria-label="缩小">−</button><button type="button" class="chipbtn" data-zoom="0">适应</button><button type="button" class="chipbtn" data-zoom="1" aria-label="放大">＋</button><span class="chipbtn dim">打开飞书画板 ↗</span></div>
        <div class="vp" id="boardVp" tabindex="0" aria-label="画板：拖动平移，按钮缩放"><div class="canvas" id="boardCanvas">
          <div class="bhead"><h3>城市记忆 · 案例方向 v${c.version}</h3><p>示例画板：仅演示版本、缩放与平移，不是真实案例内容</p></div>${cards}
        </div></div></section>`;
  }
  function vSources() {
    if (!S.sources.length) return `<h1 class="lt">原始资料</h1>${emptyBox('❖', '尚未收录材料', '飞书、本地文件和你的口述都会在这里，保留来源身份与版本。')}`;
    return `<h1 class="lt">原始资料</h1><div class="card list">${S.sources.map(s => `<div class="row"><span class="code" style="--h:${s === 'oral' ? 'var(--purple)' : 'var(--blue)'}">${SOURCES[s].kind}</span><span class="grow"><b>${esc(SOURCES[s].title)}</b><small>${SOURCES[s].meta}</small></span><button type="button" class="chipbtn" data-cite="${s}">查看引用</button></div>`).join('')}</div>`;
  }
  function vHistory() {
    if (!S.history.length) return `<h1 class="lt">修改与确认记录</h1>${emptyBox('◷', '暂无记录', '每次写入都会追加一条记录，旧版本始终可查。')}`;
    return `<h1 class="lt">修改与确认记录</h1><p class="sub">只追加，不改写。</p><ol class="hist">${S.history.slice().reverse().map(h => `<li class="${h.kind}"><time>${h.t}</time><b>${h.a}</b><span>${h.d}</span></li>`).join('')}</ol>`;
  }

  /* ── 追溯检查器 ─────────────────────────────────────────── */
  function renderInspector() {
    const q = S.inspector;
    insp.hidden = !q;
    root.classList.toggle('insp-open', !!q);
    if (!q) { insp.innerHTML = ''; return; }
    if (q.src) {
      const s = SOURCES[q.src];
      insp.innerHTML = `<header><b>来源详情</b><button type="button" class="x" data-close aria-label="关闭">✕</button></header><div class="ib">
        <p class="istep">${s.kind}</p><h4>${esc(s.title)}</h4><p class="small">${s.meta}</p>
        <blockquote>${q.src === 'oral' ? '“这轮我方执行预算按 60 万元策划。请更新 Debrief，写清预算总额，未明确的限制不要推定。”' : '“二、交付要求：首期需提交成片——8 分钟主影片，开馆日循环播放；展墙图文 3 面。三、预算：本项目预算 100 万元（含设备）。”'}</blockquote>
        <p class="small">原件与之后的决定分开保存。</p></div>`;
      return;
    }
    const [rc, bid] = q.block.split('.');
    const rv = S.reviews.find(r => r.code === rc); if (!rv) { S.inspector = null; return renderInspector(); }
    const b = rv.sections.flatMap(s => s.blocks).find(x => x.id === bid);
    const deps = b.deps.map(([c, topic]) => {
      const o = S.objects.find(x => x.code === c);
      return `<div class="idep">${code(c)}<b>${o ? o.title : ''}</b><span class="tag" style="--h:var(--green)">用 v${o ? o.rev : 1}</span><span class="grow"></span><button type="button" class="chipbtn" data-goto="${c}">前往</button><p>${esc(topic)}</p></div>`;
    }).join('');
    const srcs = [...new Set(b.deps.map(([c, t]) => S.objects.find(x => x.code === c)?.items.find(i => i.topic === t)?.src).filter(Boolean))];
    insp.innerHTML = `<header><b>完整追溯路径</b><button type="button" class="x" data-close aria-label="关闭">✕</button></header><div class="ib">
      <p class="istep"><i>1</i>当前段落</p><div class="ipara">${esc(b.text)}</div>
      <p class="istep"><i>2</i>所依据的项目信息</p>${deps}
      <p class="istep"><i>3</i>原始来源</p><div class="isrcs"><p class="small">原文引用</p>${srcs.map(cite).join('')}</div>
      <button type="button" class="chipbtn back" data-close>返回阅读</button></div>`;
  }

  /* ── 画板：拖动平移 + 缩放 ──────────────────────────────── */
  let view = {x: 0, y: 0, s: .62};
  function bindBoard() {
    const vp = $('#boardVp'), cv = $('#boardCanvas');
    const apply = () => { cv.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.s})`; };
    apply();
    let drag = null;
    vp.onpointerdown = e => { drag = {x: e.clientX - view.x, y: e.clientY - view.y}; vp.setPointerCapture(e.pointerId); vp.classList.add('grab'); };
    vp.onpointermove = e => { if (!drag) return; view.x = e.clientX - drag.x; view.y = e.clientY - drag.y; apply(); };
    vp.onpointerup = vp.onpointercancel = () => { drag = null; vp.classList.remove('grab'); };
    vp.onwheel = e => { if (!e.ctrlKey && !e.metaKey) return; e.preventDefault(); zoom(e.deltaY < 0 ? 1 : -1); };
    vp.onkeydown = e => { const d = {ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40]}[e.key]; if (d) { e.preventDefault(); view.x += d[0]; view.y += d[1]; apply(); } };
    function zoom(dir) { view.s = dir === 0 ? .62 : Math.min(1.6, Math.max(.35, view.s * (dir > 0 ? 1.2 : 1 / 1.2))); if (dir === 0) view.x = view.y = 0; apply(); }
    bindBoard.zoom = zoom;
  }

  /* ── 面板交互（事件委托） ───────────────────────────────── */
  root.addEventListener('click', e => {
    const t = e.target.closest('button, [data-view]');
    if (!t || !root.contains(t)) return;
    if (t.dataset.view) { S.view = t.dataset.view; S.inspector = null; render(); stage.scrollTop = 0; }
    else if (t.dataset.obj) { S.selDraft = t.dataset.obj; render(); }
    else if (t.dataset.review) { S.selReview = t.dataset.review; S.inspector = null; render(); }
    else if (t.dataset.trace) { S.inspector = {block: t.dataset.trace}; renderInspector(); }
    else if (t.dataset.cite) { S.inspector = {src: t.dataset.cite}; renderInspector(); }
    else if ('close' in t.dataset) { S.inspector = null; renderInspector(); }
    else if (t.dataset.goto) { S.view = 'draft'; S.selDraft = t.dataset.goto; S.inspector = null; render(); }
    else if (t.dataset.zoom !== undefined) bindBoard.zoom?.(+t.dataset.zoom);
    else if ('togglePane' in t.dataset) { root.dataset.pane = root.dataset.pane === 'open' ? 'closed' : 'open'; if (mobile()) setTab(root.dataset.pane === 'open' ? 'pane' : 'chat'); }
    else if (t.dataset.mtab) setTab(t.dataset.mtab);
    else if ('reset' in t.dataset) reset();
  });
  function setTab(tab) {
    root.dataset.mtab = tab;
    for (const b of $$('.cx-mtabs [data-mtab]', root)) b.setAttribute('aria-selected', String(b.dataset.mtab === tab));
  }

  /* ── 分隔条拖动 ─────────────────────────────────────────── */
  const split = $('#cxSplit');
  const setPane = px => {
    const body = $('.cx-body', root).getBoundingClientRect();
    const side = $('.cx-side', root).offsetWidth;
    const w = Math.max(380, Math.min(body.width - side - 300, px));
    root.style.setProperty('--pane-w', w + 'px');
  };
  split.addEventListener('pointerdown', e => {
    split.setPointerCapture(e.pointerId); root.classList.add('resizing');
    const right = $('.cx-body', root).getBoundingClientRect().right;
    const move = ev => setPane(right - ev.clientX);
    const up = () => { split.removeEventListener('pointermove', move); root.classList.remove('resizing'); };
    split.addEventListener('pointermove', move); split.addEventListener('pointerup', up, {once: true});
  });
  split.addEventListener('keydown', e => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault(); setPane($('.cx-pane', root).offsetWidth + (e.key === 'ArrowLeft' ? 40 : -40));
  });

  /* ── 对话 ───────────────────────────────────────────────── */
  const toBottom = () => { scroller.scrollTop = scroller.scrollHeight; };
  function add(html, cls) { const li = document.createElement('li'); li.className = cls; li.innerHTML = html; log.append(li); empty.hidden = true; toBottom(); return li; }
  function userMsg(text) { add(`<div class="bubble">${esc(text).replace(/\n/g, '<br>')}</div>`, 'm-user'); }
  async function think(id, ms = 900) { const li = add('<span class="shimmer">思考中</span>', 'm-think'); await sleep(ms); guard(id); li.remove(); }
  async function tool(id, verb, cmd, out, fn, ms = 700) {
    for (const prev of $$('.m-tool', log)) { prev.lastElementChild.hidden = true; prev.firstElementChild.setAttribute('aria-expanded', 'false'); }
    const actions = [['yuplus/', '了解当前工作的整理规则'], ['lark-cli docs', '阅读客户需求说明'], ['yu source import', '保存资料与原始出处'], ['yu draft apply', '整理与更新项目信息'], ['yu review prepare', '检查策划文档的依据'], ['yu review publish', '保存策划文档'], ['yu library list', '查看已登记的案例库'], ['案例库 +', '分析案例库与公开网络中的参考'], ['lark-cli whiteboard', '整理飞书案例参考板'], ['yu research create', '保存本轮案例分析']];
    const action = actions.find(([prefix]) => cmd.startsWith(prefix))?.[1] || verb;
    const li = add(`<button type="button" class="tool" aria-expanded="false" title="展开技术细节"><span class="st run"></span><span>${esc(action)}</span></button><pre class="tout" hidden>${esc(cmd)}\n${esc(out)}</pre>`, 'm-tool');
    const btn = li.firstElementChild;
    btn.onclick = () => { const o = li.lastElementChild; o.hidden = !o.hidden; btn.setAttribute('aria-expanded', String(!o.hidden)); };
    await sleep(ms); guard(id);
    if (fn) { saving.hidden = false; await fn(); guard(id); saving.hidden = true; }
    btn.firstElementChild.className = 'st ok';
    toBottom();
    await sleep(250);
  }
  async function aiMsg(id, parts) {
    if (mobile()) setTab('chat');
    const li = add('<div class="ai"></div>', 'm-ai');
    const box = li.firstElementChild;
    for (const [label, text] of parts) {
      const p = document.createElement('p');
      p.innerHTML = label ? `<b>${label}</b>` : '';
      const span = document.createElement('span'); p.append(span); box.append(p);
      if (fast) { span.textContent = text; continue; }
      for (let i = 0; i <= text.length; i += 2) { guard(id); span.textContent = text.slice(0, i); toBottom(); await sleep(14); }
      span.textContent = text;
    }
    toBottom();
  }

  /* ── 面板写入辅助 ───────────────────────────────────────── */
  function show(v, extra) {
    root.dataset.pane = 'open';
    if (mobile()) setTab('pane');
    Object.assign(S, {view: v, inspector: null}, extra || {});
    render();
  }
  function reveal(sel) {
    const el = $(sel, stage); if (!el) return;
    const a = el.getBoundingClientRect(), b = stage.getBoundingClientRect();
    if (a.bottom > b.bottom - 16 || a.top < b.top) stage.scrollTo({top: stage.scrollTop + a.top - b.top - 90, behavior: fast ? 'auto' : 'smooth'});
  }
  async function writeItem(id, obj, it) {
    const k = obj.code + '.' + it.id;
    if (it.fields) it.fields.forEach((_, i) => { tw[k + '.' + i] = 0; }); else tw[k] = 0;
    obj.items.push(it); S.selDraft = obj.code; S.flash = k; render(); reveal(`[data-item="${CSS.escape(k)}"]`);
    if (it.fields) for (let i = 0; i < it.fields.length; i++) await type(id, k + '.' + i, it.fields[i][1], 26);
    else await type(id, k, it.text);
    await sleep(180);
  }
  async function writeBlock(id, rv, sec, b) {
    const k = rv.code + '.' + b.id; tw[k] = 0;
    let s = rv.sections.find(x => x.h === sec);
    if (!s) { s = {h: sec, blocks: []}; rv.sections.push(s); }
    s.blocks.push(b); S.flash = k; render(); reveal(`[data-block="${CSS.escape(k)}"], .rp:last-of-type`);
    await type(id, k, b.text, 22);
    await sleep(160);
  }
  const hist = (kind, a, d, add) => S.history.push({t: stamp(add), kind, a, d});

  /* ── 四个预设场景 ───────────────────────────────────────── */
  const SCENES = [
    {key: 'collect', n: '01', label: '添加资料', text: '这是「城市记忆展厅」的客户 Brief，请整理项目目标、受众、预算和交付要求，标出还需要确认的问题。\nhttps://example.feishu.cn/docx/CityMemoryV3', run: sCollect},
    {key: 'organize', n: '02', label: '整理策划文档', text: '根据已有资料，整理一版主策 Debrief，说明项目背景、职责边界、受众与交付要求；相关推进安排也请一并整理。', needs: 'collect', run: sOrganize},
    {key: 'revise', n: '03', label: '提出修改', text: '这轮我方执行预算按 60 万元策划。请更新 Debrief，写清预算总额，未明确的限制不要推定。', needs: 'organize', run: sRevise},
    {key: 'cases', n: '04', label: '案例分析', text: '分析几个旧工业建筑改造成展览空间的案例，重点看它们如何利用原有建筑讲故事，提炼对本项目有启发的空间与叙事方法。', run: sCases}
  ];

  async function sCollect(id) {
    await think(id);
    await tool(id, '读取', 'yuplus/SKILL.md', '技能已加载 · 场景：项目信息（draft）\n按需读取 references/materials.md');
    await tool(id, '运行', 'lark-cli docs +fetch --doc CityMemoryV3', '《城市记忆展厅｜项目需求与预算说明（V3）》\n6,140 字 · revision 18', null, 900);
    await tool(id, '运行', 'yu source import --project prj_city --input source.json', '{"ok": true, "source_id": "src_brief", "snapshot": 1}', async () => {
      S.sources.push('brief'); hist('chg', '收录来源', '飞书《城市记忆展厅｜项目需求与预算说明（V3）》· 快照 v1', 2);
      show('sources'); await sleep(900);
    });
    await tool(id, '运行', 'yu draft apply --project prj_city --input draft.json', '{"ok": true, "objects": 4, "items": 7, "revision": 1}', async () => {
      const t = stamp(1).slice(6); show('draft');
      const D = (c, title) => { const o = {code: c, title, rev: 1, time: '2026-10-16 ' + t, items: []}; S.objects.push(o); return o; };
      const d01 = D('D01', 'BD 同步信息');
      await writeItem(id, d01, {id: 'bg', topic: '项目背景', kind: 'statement', src: 'brief', text: '市文旅局拟在滨江旧仓改造常设展厅，2027 年春季开馆。首期以「城市记忆」为主线，覆盖三个历史断面。'});
      await writeItem(id, d01, {id: 'why', topic: '客户为何现在做', kind: 'statement', src: 'brief', text: '今年有文旅专项拨款窗口，年底前需完成立项采购。'});
      const d07 = D('D07', '总预算区间');
      await writeItem(id, d07, {id: 'client', topic: '客户预算', kind: 'statement', src: 'brief', fields: [['金额', '100 万元（含设备）'], ['范围', '本轮项目预算']]});
      const d09 = D('D09', '时间节点或区间');
      await writeItem(id, d09, {id: 'open', topic: '开馆', kind: 'statement', src: 'brief', fields: [['时间', '2027 年春季'], ['性质', '客户目标']]});
      await writeItem(id, d09, {id: 'dir', topic: '方向评审', kind: 'statement', src: 'brief', fields: [['日期', '2026-12-20'], ['内容', '创意方向评审']]});
      const d18 = D('D18', '交付细节');
      await writeItem(id, d18, {id: 'film', topic: '主影片', kind: 'statement', src: 'brief', fields: [['形态', '成片 · 约 8 分钟'], ['要求', '开馆日循环播放']]});
      await writeItem(id, d18, {id: 'wall', topic: '展墙图文', kind: 'statement', src: 'brief', fields: [['数量', '3 面'], ['要求', '与主影片同一主线']]});
      S.flash = null; hist('chg', '整理项目信息', 'D01 · D07 · D09 · D18，共 7 个条目，均标注原文定位', 0);
    });
    await aiMsg(id, [
      ['本次读取：', '飞书《城市记忆展厅｜项目需求与预算说明（V3）》全文，已保存为来源快照 v1。'],
      ['本次修改：', '整理了项目背景、预算、时间与交付要求，共 7 条信息，均保留原文出处；材料没有明确受众，已保留为待补充。'],
      ['下一步建议：', '可以补一份开工会纪要或口头说明，澄清受众与客户决策人；也可以先按已有信息整理一版主策 Debrief，由你选择。']
    ]);
  }

  async function sOrganize(id) {
    await think(id);
    await tool(id, '读取', 'yuplus/references/review-structure.md', 'R01 固定栏目：BD同步信息 · 职责边界 · 受众 · 交付细节\nD09 + D18 有内容时同时整理 R02');
    await tool(id, '运行', 'yu review prepare --project prj_city --input prepare.json', '可整理：R01 主策 Debrief、R02 项目推进安排\n缺少依据：D06 受众、D20 职责边界');
    await tool(id, '运行', 'yu review publish --project prj_city --input r01.json', '{"ok": true, "object": "R01", "version": 1, "blocks": 6}', async () => {
      const rv = {code: 'R01', title: '主策 Debrief', version: 1, time: '2026-10-16 ' + stamp(3).slice(6), stale: false, sections: []};
      S.reviews.push(rv); show('review', {selReview: 'R01'});
      await writeBlock(id, rv, 'BD同步信息', {id: 'why', deps: [['D01', '客户为何现在做'], ['D01', '项目背景']], text: '客户今年启动本项目，与年底前必须完成立项采购的窗口直接相关。文旅局拟借滨江旧仓改造，建立常设展陈的首期叙事框架。'});
      await writeBlock(id, rv, 'BD同步信息', {id: 'goal', deps: [['D01', '项目背景'], ['D18', '主影片']], text: '要在开馆日交付可循环播放的主影片与展墙图文，形成一条能被本地市民识别的「城市记忆」主线。'});
      await writeBlock(id, rv, '职责边界', {id: 'resp', unknown: true, deps: [], text: '尚无依据：客户决策人与内部分工还没有记录，可补充开工会纪要或 BD 同步。'});
      await writeBlock(id, rv, '受众', {id: 'aud', unknown: true, deps: [], text: '尚无依据：现有材料没有受众信息。'});
      await writeBlock(id, rv, '交付细节', {id: 'scope', deps: [['D18', '主影片'], ['D18', '展墙图文']], text: '本轮交付主影片 1 支（约 8 分钟、开馆日循环播放）与 3 面展墙图文。'});
      await writeBlock(id, rv, '交付细节', {id: 'budget', deps: [['D07', '客户预算']], text: '本轮项目预算 100 万元（含设备）。'});
      S.flash = null; hist('chg', '生成策划文档', 'R01 主策 Debrief v1 · 6 个段落，2 个栏目标为尚无依据', 0);
    });
    await tool(id, '运行', 'yu review publish --project prj_city --input r02.json', '{"ok": true, "object": "R02", "version": 1, "blocks": 2}', async () => {
      const rv = {code: 'R02', title: '项目推进安排', version: 1, time: '2026-10-16 ' + stamp(1).slice(6), stale: false, sections: []};
      S.reviews.push(rv); show('review', {selReview: 'R02'});
      await writeBlock(id, rv, '时间节点或区间', {id: 'nodes', deps: [['D09', '方向评审'], ['D09', '开馆']], text: '2026-12-20 创意方向评审；2027 年春季开馆。'});
      await writeBlock(id, rv, '交付细节', {id: 'deliver', deps: [['D18', '主影片'], ['D18', '展墙图文']], text: '本轮推进围绕主影片与 3 面展墙图文展开。'});
      S.flash = null; S.selReview = 'R01'; render();
      hist('chg', '生成策划文档', 'R02 项目推进安排 v1 · 2 个段落', 0);
    });
    await aiMsg(id, [
      ['本次读取：', '已保存的项目背景、预算、时间与交付要求。'],
      ['本次修改：', '生成了主策 Debrief 与项目推进安排，每段都能查看依据。职责边界与受众仍需补充，已明确标出。'],
      ['下一步建议：', '在 Yu+ 面板里任意段落点「完整追溯路径」，可以一路查到飞书原文。']
    ]);
  }

  async function sRevise(id) {
    await think(id);
    await tool(id, '运行', 'yu source import --project prj_city --kind oral', '{"ok": true, "source_id": "src_oral", "speaker": "主策"}', async () => {
      S.sources.push('oral'); hist('chg', '收录来源', '主策口述：“本轮按 60 万推进”', 4);
    });
    await tool(id, '运行', 'yu draft apply --project prj_city --input d07.json', '{"ok": true, "object": "D07", "revision": 2, "decision": "dec_budget_60"}', async () => {
      const d07 = S.objects.find(o => o.code === 'D07');
      d07.rev = 2; d07.time = '2026-10-16 ' + stamp(1).slice(6); show('draft', {selDraft: 'D07'});
      await sleep(500);
      await writeItem(id, d07, {id: 'adopted', topic: '采用预算', kind: 'decision', src: 'oral', fields: [['金额', '60 万元'], ['范围', '本轮我方执行预算'], ['决定人', '主策']]});
      S.flash = null; render();
      hist('dec', '保存决策', 'D07 第 2 版：本轮按 60 万元推进；客户原文 100 万保留', 0);
    });
    await tool(id, '运行', 'yu draft apply --project prj_city --input guide.json', '{"ok": true, "expression_guide": "review:R01", "intent": "rewrite"}', async () => {
      hist('chg', '写入编写依据', 'R01 · 预算段只说当前预算与限制', 0);
      const r01 = S.reviews.find(r => r.code === 'R01'); r01.stale = true;
      show('review', {selReview: 'R01'}); stage.scrollTop = 0; await sleep(1300);
    });
    await tool(id, '运行', 'yu review prepare --project prj_city --input prepare.json', '受影响：R01 · 交付细节 · 1 个段落\nR02 未受影响，保持 v1');
    await tool(id, '运行', 'yu review publish --project prj_city --input r01.json', '{"ok": true, "object": "R01", "version": 2, "changed_blocks": 1}', async () => {
      const r01 = S.reviews.find(r => r.code === 'R01');
      const b = r01.sections.flatMap(s => s.blocks).find(x => x.id === 'budget');
      r01.stale = false; r01.version = 2; r01.time = '2026-10-16 ' + stamp(2).slice(6);
      b.old = b.text; b.text = '本轮我方执行预算按 60 万元推进。'; b.deps = [['D07', '采用预算']];
      const k = 'R01.budget'; tw[k] = 0; S.flash = k; render(); reveal(`[data-block="${k}"]`);
      await sleep(400); await type(id, k, b.text, 30);
      S.flash = null; hist('chg', '更新策划文档', 'R01 主策 Debrief v2 · 只改预算这一段；v1 仍可查', 0);
    });
    await aiMsg(id, [
      ['本次读取：', '你的预算调整说明（已保留原话），以及当前预算信息与主策 Debrief。'],
      ['本次修改：', '预算信息新增「当前采用：60 万元」，客户原文的 100 万保留为原文信息；预算段的表达要求记入编写依据；主策 Debrief 更新到 v2，只改了预算这一段；项目推进安排不受影响。'],
      ['下一步建议：', '如需发给团队，可以让我将当前策划文档整理到飞书，核验后返回链接。之后有改动时，可再次要求生成。']
    ]);
  }

  async function sCases(id) {
    await think(id);
    await tool(id, '读取', 'yuplus/references/case-research.md', '案例分析是独立工作流 · 新一轮研究建立 v1');
    await tool(id, '运行', 'yu library list --json', '2 个案例库：OUTPUT 案例库（飞书文件夹）· 示例参考网站');
    await tool(id, '检索', '案例库 + 公开网络', '阅读 14 个案例页面 · 截图留证 · 入选 5 个', null, 1400);
    await tool(id, '运行', 'lark-cli whiteboard +create', '飞书画板已创建 · 证据索引已保存到飞书');
    await tool(id, '运行', 'yu research create --project prj_city', '{"ok": true, "research": "case_city_v1", "version": 1}', async () => {
      const H = ['#5e8bd6', '#c77d4a', '#7a8f6a', '#8a6ab8', '#4a9aa8'];
      S.cases = {version: 1, cards: [
        {title: '示例 A · 旧仓里的影像长廊', ref: '空间叙事', why: '沿仓库长轴布置连续影像，与江线动线一致。'},
        {title: '示例 B · 口述声音档案墙', ref: '互动体验', why: '用声音承载普通人的记忆，为口述史留出呼吸空间。'},
        {title: '示例 C · 码头物件档案', ref: '概念', why: '以工具、票据为线索的档案式陈列。'},
        {title: '示例 D · 城市变迁投影沙盘', ref: '技术 / 制作', why: '分层投影，可独立于主影片运行。'},
        {title: '示例 E · 保留桁架与砖墙', ref: '视觉', why: '工业肌理作为展墙图文的底色。'}
      ].map((c, i) => ({...c, h: H[i], x: 60 + (i % 3) * 330, y: 150 + Math.floor(i / 3) * 360, shown: false}))};
      view = {x: 0, y: 0, s: .62};
      show('cases'); hist('chg', '案例分析', '研究 v1 · 5 个示例案例 · 画板与证据在飞书', 3);
      for (const c of S.cases.cards) { await sleep(420); guard(id); c.shown = true; render(); }
    });
    await aiMsg(id, [
      ['本次读取：', '2 个已登记案例库与公开网络，阅读了 14 个案例页面。'],
      ['本次修改：', '开启案例分析 v1，入选 5 个案例；画板与证据索引保存在飞书。Yu+ 只记录版本和画板位置，没有改动项目信息或策划文档。'],
      ['下一步建议：', '画板可以拖动和缩放。要换方向就说「开一轮新的案例分析」，会建立 v2，v1 保留。']
    ]);
  }

  /* ── 运行 ───────────────────────────────────────────────── */
  function available(sc) { return !S.done.has(sc.key) && (!sc.needs || S.done.has(sc.needs)); }
  function renderSuggest() {
    const left = SCENES.filter(sc => !S.done.has(sc.key));
    if (!left.length) {
      suggest.innerHTML = `<p class="sg-done">四个场景都试过了。点 Yu+ 面板里段落的「完整追溯路径」，或<button type="button" class="sg-link" data-reset>重新开始</button></p>`;
      return;
    }
    suggest.innerHTML = left.map(sc => {
      const ok = available(sc);
      return `<button type="button" class="sg${ok ? '' : ' wait'}" role="listitem" data-scene="${sc.key}" ${ok && !busy ? '' : 'disabled'} title="${ok ? '' : '先完成：' + SCENES.find(x => x.key === sc.needs).label}"><span class="n">${sc.n}</span><b>${sc.label}</b><span class="t">${esc(sc.text.split('\n')[0])}</span></button>`;
    }).join('');
  }
  suggest.addEventListener('click', e => {
    const b = e.target.closest('[data-scene]'); if (!b || busy) return;
    const sc = SCENES.find(x => x.key === b.dataset.scene);
    input.value = sc.text; input.dataset.scene = sc.key; input.focus();
    form.requestSubmit();
  });
  function pick(text) {
    const hint = input.dataset.scene && SCENES.find(x => x.key === input.dataset.scene);
    if (hint && available(hint)) return hint;
    const rules = [['cases', /案例|画板|参考/], ['revise', /万|预算|改|修/], ['organize', /整理|debrief|review|成果/i], ['collect', /文档|材料|飞书|收/]];
    for (const [k, re] of rules) { const sc = SCENES.find(x => x.key === k); if (re.test(text) && available(sc)) return sc; }
    return SCENES.find(available);
  }
  async function run(sc, text) {
    const id = ++runId; busy = true; setBusy(true); renderSuggest();
    userMsg(text);
    try { await sc.run(id); S.done.add(sc.key); }
    catch (err) { if (err !== CANCEL) throw err; return; }
    finally { if (id === runId) { busy = false; fast = reduced; saving.hidden = true; setBusy(false); renderSuggest(); } }
  }
  function setBusy(b) { sendBtn.disabled = b; skipBtn.hidden = !b; root.classList.toggle('busy', b); }
  form.addEventListener('submit', e => {
    e.preventDefault();
    if (busy) return;
    const text = input.value.trim();
    if (!text) { input.focus(); return; }
    const sc = pick(text);
    input.value = ''; delete input.dataset.scene;
    if (!sc) return;
    run(sc, text);
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
  skipBtn.addEventListener('click', () => { fast = true; });

  // 自动演示：逐字输入并发送剩余场景
  async function autoplay() {
    document.getElementById('try').scrollIntoView({behavior: reduced ? 'auto' : 'smooth', block: 'start'});
    if (busy) return;
    if (!SCENES.some(available)) reset();
    const id0 = runId;
    for (const sc of SCENES) {
      if (!available(sc)) continue;
      await sleep(500); if (runId !== id0 && busy) return;
      for (let i = 0; i <= sc.text.length; i += 1) { input.value = sc.text.slice(0, i); await sleep(reduced ? 0 : 28); }
      input.dataset.scene = sc.key;
      const before = runId; form.requestSubmit();
      while (busy) await new Promise(r => setTimeout(r, 120));
      if (runId !== before + 1 || !S.done.has(sc.key)) return;
      await sleep(900);
    }
  }
  for (const b of $$('[data-autoplay]')) b.addEventListener('click', autoplay);

  // 引导：窗口进入视野时，把第一句预填进输入框，等访客按下发送
  reset();
  let primed = false;
  const io = 'IntersectionObserver' in window && new IntersectionObserver(async entries => {
    if (primed || !entries.some(e => e.isIntersecting)) return;
    primed = true; io.disconnect();
    if (busy || input.value || log.children.length) return;
    const sc = SCENES[0];
    for (let i = 0; i <= sc.text.length; i++) {
      if (busy || log.children.length) return;
      input.value = sc.text.slice(0, i); await sleep(reduced ? 0 : 24);
    }
    input.dataset.scene = sc.key; sendBtn.classList.add('ready');
  }, {threshold: .45});
  if (io) io.observe(root);
  form.addEventListener('submit', () => sendBtn.classList.remove('ready'));
})();
