/* ═══════════════════════════════════════════════════════════════════════════
   Yu+ 只读浏览界面
   本文件只读取服务提供的数据并渲染，模拟预览必须由服务明确声明。没有任何写入路径：没有编辑、批准、删除、上传，
   没有页面内聊天或评论。业务写入一律在 Codex 中由 Agent 通过 Yu+ CLI 完成。
   ═══════════════════════════════════════════════════════════════════════════ */

import { loadView } from "./data/runtime.js";
let DATA;
import { basisStatus, qaState, openQuestionState } from "./data/selectors.js";
import { expandBasis, changedBasisDetails } from "./data/provenance.js";
import { compareBasisItems } from "./data/basis-diff.js";
import { reviewUpdatePrompt, reviewExportPrompt } from "./data/review-prompts.js";
import { milestoneDates, parseScheduleTime, timelineScale } from "./data/timeline.js";
import { moneyMatches, formatMinor } from "./data/money-text.js";
import { projectMonitors, projectMonitorSummary, monitorSummary, monitorPrompt, monitorRuns, monitorRunStatus, safeChatUrl } from "./data/monitoring.js";
let pageLoadedAt = new Date();
const S = { route: null, inspector: null, expanded: {}, showAllTypes: false, directoryCollapsed: true, mainNavCollapsed: false, versionOf: {} };

/* ── 基础工具 ───────────────────────────────────────────────────────────── */
const $ = (id) => document.getElementById(id);
const el = (t, c) => { const n = document.createElement(t); if (c) n.className = c; return n; };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const T = (s, fb = "尚未记录") => (s === null || s === undefined || s === "" ? fb : String(s));
const byId = (arr, id) => arr.find((x) => x.id === id) || null;

const oOf = (id) => byId(DATA.objects, id);
const revOf = (id) => DATA.indexes.revById[id] || null;
const headRev = (obj) => (obj && obj.current_revision_id ? revOf(obj.current_revision_id) : null);
const svOf = (id) => DATA.indexes.svById[id] || null;
const srcOf = (id) => DATA.indexes.srcById[id] || null;
const srcOfSv = (sv) => (sv ? srcOf(sv.source_id) : null);
const projOf = (id) => byId(DATA.projects, id);
const revsOf = (oid) => DATA.object_revisions.filter((r) => r.object_id === oid).sort((a, b) => a.version - b.version);

const typeMeta = (tk) =>
  DATA.catalog.find((c) => c.type_key === tk) ||
  DATA.REVIEW_KINDS.find((r) => r.type_key === tk) ||
  DATA.internal_types.find((t) => t.type_key === tk) || null;
const typeCode = (tk) => { const m = typeMeta(tk); return m && m.code ? m.code : null; };
const typeName = (tk) => { const m = typeMeta(tk); return m ? m.name : tk; };
const HUE = { blue: "var(--blue)", orange: "var(--orange)", teal: "var(--teal)", purple: "var(--purple)", indigo: "var(--indigo)", green: "var(--green)", gray: "var(--gray)", red: "var(--red)", pink: "var(--pink)", yellow: "var(--yellow)", mint: "var(--mint)", brown: "var(--brown)" };
const hueOf = (name) => HUE[name] || "var(--gray)";
const themeOf = (tk) => DATA.THEMES.find((t) => t.types.includes(tk)) || null;
const typeHue = (tk) => { const th = themeOf(tk); return th ? hueOf(th.hue) : "var(--gray)"; };

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const p = (n) => String(n).padStart(2, "0");
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff >= 0 && diff < 86400 * 3) {
    const m = Math.floor(diff / 60);
    if (m < 1) return "刚刚";
    if (m < 60) return m + " 分钟前";
    const h = Math.floor(m / 60);
    if (h < 24) return h + " 小时前";
    return Math.floor(h / 24) + " 天前";
  }
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
const fullTime = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
// 金额以最小货币单位保存：分 → 可读金额，保留币种；未知不显示为零
const money = formatMinor;

function highlightMoney(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.parentElement.closest('.money, code, script, style, textarea, select')) continue;
    const matches = moneyMatches(node.data);
    if (!matches.length) continue;
    const fragment = document.createDocumentFragment();
    let offset = 0;
    for (const match of matches) {
      fragment.append(document.createTextNode(node.data.slice(offset, match.index)));
      const span = el('span', 'money'); span.textContent = match.text; fragment.append(span);
      offset = match.index + match.text.length;
    }
    fragment.append(document.createTextNode(node.data.slice(offset)));
    node.replaceWith(fragment);
  }
}

const proseWidths = new WeakMap();
const proseObserver = new ResizeObserver(entries => {
  for (const { target, contentRect } of entries) {
    if (proseWidths.get(target) === contentRect.width) continue;
    proseWidths.set(target, contentRect.width);
    updateProseToggle(target);
  }
});
function updateProseToggle(node) {
  if (!node.getClientRects().length) return;
  const lineHeight = parseFloat(getComputedStyle(node).lineHeight);
  const long = node.scrollHeight > lineHeight * 3 + 1;
  node.classList.toggle('is-collapsible', long);
  if (long) {
    node.tabIndex = 0;
    node.setAttribute('role', 'button');
    const expanded = node.classList.contains('is-expanded');
    node.setAttribute('aria-expanded', String(expanded));
    node.title = expanded ? '点击收起正文' : '点击展开全文';
  } else {
    node.classList.remove('is-expanded');
    for (const attr of ['tabindex', 'role', 'aria-expanded', 'title']) node.removeAttribute(attr);
  }
}
function initProseToggles() {
  proseObserver.disconnect();
  for (const node of document.querySelectorAll('.item .prose, .item .field dd, .resource-scope p, .timeline-note > p, .delivery-entry > p, .btext p, .tlrow > div:not(.t)')) {
    if (node.querySelector('button, a, input, .tag')) continue;
    node.classList.add('collapsible-prose');
    updateProseToggle(node);
    const toggle = () => {
      if (!node.classList.contains('is-collapsible')) return;
      node.classList.toggle('is-expanded');
      updateProseToggle(node);
    };
    node.onclick = () => { if (!window.getSelection()?.toString()) toggle(); };
    node.onkeydown = event => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (!node.classList.contains('is-collapsible')) return;
      event.preventDefault(); toggle();
    };
    proseObserver.observe(node);
  }
}

function addSourceTypePopover(card, kind, id) {
  const meta = DATA.EPISTEMIC[kind];
  const label = el('span', 'source-type-popover');
  label.id = id;
  label.setAttribute('role', 'tooltip');
  if (!card.style.getPropertyValue('--h')) card.style.setProperty('--h', hueOf(meta?.hue || 'gray'));
  label.textContent = meta?.label || kind;
  card.classList.add('has-source-type');
  card.tabIndex = 0;
  card.setAttribute('aria-describedby', id);
  card.append(label);
}

/* ── 小部件 ─────────────────────────────────────────────────────────────── */
function setPanelToggleIcon(button, collapsed) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("width", "20"); icon.setAttribute("height", "20");
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = `<g fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M9 4v16"/><path d="${collapsed ? "m13 9 3 3-3 3" : "m16 9-3 3 3 3"}"/></g>`;
  button.replaceChildren(icon);
}
function tag(text, hue, dot) {
  const s = el("span", "tag");
  if (hue) s.style.setProperty("--h", hueOf(hue));
  s.append(document.createTextNode(text));
  if (dot) { const d = el("i", "d"); s.prepend(d); }
  return s;
}
function codeChip(code, hue) {
  const s = el("span", "code");
  s.style.setProperty("--h", hueOf(hue));
  s.textContent = code;
  return s;
}
function epistemicTag(kind) {
  const m = DATA.EPISTEMIC[kind];
  return tag(m ? m.label : kind, m ? m.hue : "gray", true);
}
function providerTag(provider) {
  const m = DATA.PROVIDERS[provider];
  return tag(m ? m.label : provider, m ? m.hue : "gray");
}
function btn(label, onclick, cls) {
  const b = el("button", "btn" + (cls ? " " + cls : ""));
  b.type = "button"; b.textContent = label; b.onclick = onclick;
  return b;
}
function chipBtn(label, onclick) {
  const b = el("button", "chipbtn");
  b.type = "button"; b.textContent = label; b.onclick = onclick;
  return b;
}
let localFileCapabilities;
function addFileAction(container, version, asset) {
  if (asset.availability !== 'available') return;
  const download = () => {
    if (!asset.download_url) return;
    const link = el('a', 'chipbtn');
    link.href = asset.download_url; link.download = asset.display_name;
    link.textContent = '下载'; link.title = '按原文件名下载已保存的附件';
    container.append(link);
  };
  if (asset.storage !== 'external') { download(); return; }
  const projectId = S.route.pid;
  localFileCapabilities ||= fetch("/api/local-files" + (DATA.meta.demo ? "" : "?project=" + encodeURIComponent(S.route.pid))).then((response) => response.ok ? response.json() : null).catch(() => null);
  localFileCapabilities.then((capabilities) => {
    if (!capabilities?.supported || !capabilities.files.some((file) => file.versionId === version.id && file.assetId === asset.asset_id)) { download(); return; }
    const status = el("div", "tiny muted"); status.setAttribute("role", "status");
    const button = chipBtn("在 Finder 中显示", async () => {
      button.disabled = true; status.textContent = "";
      try {
        const response = await fetch("/api/local-files/reveal", {
          method:"POST", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({...(!DATA.meta.demo ? {projectId} : {}),versionId:version.id,assetId:asset.asset_id}),
        });
        const result = await response.json();
        status.textContent = result.message || result.error?.message || (response.ok ? "已在 Finder 中显示" : "无法定位本地文件");
      } catch { status.textContent = "无法连接本地文件服务"; }
      finally { button.disabled = false; }
    });
    button.classList.add("reveal-file");
    button.title = "在 Finder 中显示已登记的本地原文件";
    container.append(button, status);
  });
}
function kv(pairs) {
  const dl = el("dl", "kv");
  for (const [k, v] of pairs) {
    const dt = el("dt"); dt.textContent = k; dl.append(dt);
    const dd = el("dd");
    if (v instanceof Node) dd.append(v); else dd.textContent = T(v);
    dl.append(dd);
  }
  return dl;
}
function banner(hue, icon, nodes) {
  const b = el("div", "banner");
  b.style.setProperty("--h", hueOf(hue));
  const i = el("span", "ic"); i.textContent = icon; b.append(i);
  const g = el("div", "grow");
  for (const n of nodes) g.append(n);
  b.append(g);
  return b;
}
function empty(glyph, title, lines) {
  const e = el("div", "empty");
  const g = el("div", "glyph"); g.textContent = glyph; e.append(g);
  const h = el("h3"); h.textContent = title; e.append(h);
  for (const l of lines || []) { const p = el("p"); p.textContent = l; e.append(p); }
  return e;
}
async function copyText(text, node) {
  const original = node.textContent;
  try { await navigator.clipboard.writeText(text); node.textContent = "已复制"; }
  catch { node.textContent = "无法复制"; }
  setTimeout(() => { node.textContent = original; }, 1400);
}

/* 交给 Agent 的引用：带项目身份、对象/来源身份、条目或段落、所看版本与可读名称 */
function copyRefButton(spec) {
  const lines = [
    "Yu+ 引用",
    `项目：${spec.project_name}（${spec.project_id}）`,
    `对象：${spec.object_label}`,
  ];
  if (DATA.meta?.demo === false) lines.push(`数据目录：${DATA.meta.data_dir}`);
  if (spec.item_label) lines.push(`条目：${spec.item_label}`);
  if (spec.block_label) lines.push(`段落：${spec.block_label}`);
  lines.push(`版本：${spec.version_label}`);
  if (spec.source_label) lines.push(`来源：${spec.source_label}`);
  if (spec.excerpt) lines.push(`原文：${spec.excerpt}`);
  const text = lines.join("\n");
  const b = chipBtn("复制引用", () => {});
  b.title = text;
  b.onclick = () => copyText(text, b);
  return b;
}

/* ── 飞书 / 来源 标题链接组件 ────────────────────────────────────────────
   两个动作严格分开：标题 → 打开原文（新标签）；「查看引用」→ 本地来源快照。
   ─────────────────────────────────────────────────────────────────────── */
function sourceLink(sv_id, opts) {
  const sv = svOf(sv_id);
  if (!sv) { const s = el("span", "muted small"); s.textContent = "来源快照未记录"; return s; }
  const src = srcOfSv(sv);
  const provider = src ? src.provider : "local";
  const prov = DATA.PROVIDERS[provider] || { label: provider, hue: "gray" };
  const hue = hueOf(prov.hue);

  const wrap = el("span", "flink");
  wrap.style.setProperty("--h", hue);

  // 类型标识
  const tp = el("span", "type");
  tp.textContent = prov.label;
  wrap.append(tp);

  // 标题：已取得标题就显示真实标题；只有裸链接时不编造
  const hasTitle = !!(src && src.cached_title);
  const title = el("a", "title");
  if (opts && opts.inline) title.style.padding = "3px 10px";
  const txt = el("span");
  if (hasTitle) {
    txt.textContent = src.cached_title;
  } else {
    wrap.classList.add("untitled");
    txt.textContent = `${prov.label}材料（标题尚未取得）`;
  }
  title.append(txt);
  // 原件属于被引用的快照，不跟随来源最新版本，也不把提取正文当成原件。
  const originals = (sv.assets || []).filter((asset) => asset.role === "original");
  const files = originals.length ? originals : (sv.assets || []);
  const localFile = provider === "local" && files.length === 1 &&
    ["available", "local_copy"].includes(files[0].availability) ? files[0] : null;
  const originalUrl = src?.canonical_url || localFile?.url;
  if (originalUrl) {
    title.href = originalUrl;
    title.target = "_blank";
    title.rel = "noopener noreferrer";
    title.title = DATA.meta.demo ? "在新标签页打开示例原文（本地模拟）" : "在新标签页打开原文";
    const ext = el("span"); ext.textContent = "↗"; ext.style.opacity = ".7"; ext.style.fontSize = "12px";
    title.append(ext);
  } else {
    title.href = "#";
    title.title = "查看此版本的来源正文与文件（未保存可直接打开的唯一原件）";
    title.onclick = (e) => { e.preventDefault(); openInspector({ kind: "source", id: sv.source_id, sv: sv.id }); };
  }
  wrap.append(title);

  // 独立控件：查看本地保存的来源快照
  const x = el("button", "xref");
  x.type = "button";
  x.title = "查看 Yu+ 保存的来源快照（不打开原文）";
  x.textContent = "查看引用";
  x.onclick = () => openInspector({ kind: "source", id: sv.source_id, sv: sv.id });
  wrap.append(x);

  return wrap;
}

function sourceLinksOf(item) {
  const box = el("div", "cites");
  const refs = item.source_refs || [];
  if (!refs.length) return box;
  for (const r of refs) {
    const lbl = el("span", "tiny muted");
    lbl.textContent = "依据";
    lbl.style.marginRight = "-2px";
    const row = el("div", "source-row");
    row.append(lbl, sourceLink(r.source_version_id, { inline: true }));
    box.append(row);
  }
  return box;
}

/* ── 依据变化检测 ────────────────────────────────────────────────────────
   只比较可验证的依赖版本：段落依据的 draft 版本 vs 该对象当前版本。
   不比较整对象版本号来断言全部段落失效。
   ─────────────────────────────────────────────────────────────────────── */
function blockBasisStatus(block_id, rev) {
  const lg = rev.block_lineage && rev.block_lineage[block_id];
  if (!lg) return { known: false, stale: [], lineage: null };
  const stale = (lg.basis || []).filter((b) => basisStatus(DATA, b) === "changed");
  return { known: (lg.basis || []).every(b => basisStatus(DATA,b) !== "unknown"), stale, lineage: lg };
}

/* 反向索引：某来源被哪些 draft 条目引用 */
function itemsUsingSourceVersion(sv_id) {
  const out = [];
  for (const r of DATA.object_revisions) {
    if (!r.payload || !r.payload.items) continue;
    for (const it of r.payload.items) {
      for (const ref of it.source_refs || []) {
        if (ref.source_version_id === sv_id) {
          const o = oOf(r.object_id);
          if (!o) continue;
          out.push({ object: o, revision: r, item: it, evidence_kind: ref.evidence_kind, locator: ref.locator });
        }
      }
    }
  }
  // 同一对象只保留其当前版本上的引用，避免把历史版本重复计入
  const seen = new Set();
  return out.filter((x) => {
    const o = x.object;
    if (o.current_revision_id !== x.revision.id) return false;
    const key = o.id + "::" + x.item.item_id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/* 对象的直接上下游 */
function relationsOf(object_id, item_id) {
  const rev = headRev(oOf(object_id));
  const up = [], down = [];
  if (rev && rev.payload && rev.payload.items) {
    for (const it of rev.payload.items) {
      if (item_id && it.item_id !== item_id) continue;
      for (const d of it.dependencies || []) {
        up.push({ kind: d.dependency_kind, object: oOf(d.producer_object_id), item_id: d.producer_item_id, via_item: it.item_id });
      }
    }
  }
  for (const r of DATA.object_revisions) {
    if (!r.payload || !r.payload.items || oOf(r.object_id)?.current_revision_id !== r.id) continue;
    for (const it of r.payload.items) {
      for (const d of it.dependencies || []) {
        if (d.producer_object_id === object_id && (!item_id || d.producer_item_id === item_id)) {
          down.push({ kind: d.dependency_kind, object: oOf(r.object_id), item_id: it.item_id });
        }
      }
    }
  }
  return { up, down };
}

/* ═══════════════════════════ 检查器 ═══════════════════════════════════ */
function openInspector(spec) {
  S.inspector = spec; render();
  const panel = document.querySelector(".inspector");
  if (panel) { panel.tabIndex = -1; panel.focus({ preventScroll: true });
    if (window.innerWidth < 1180) panel.scrollIntoView({ behavior: "smooth", block: "start" }); }
}
function closeInspector() {
  S.inspector = null; render();
  const heading = document.querySelector("main h1");
  if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); }
}

function renderInspector() {
  const spec = S.inspector;
  const box = el("div", "inspector");
  const head = el("div", "ihead");
  const h = el("h3");
  const close = el("button", "close"); close.setAttribute("aria-label", "关闭详情"); close.type = "button"; close.textContent = "✕";
  close.title = "关闭"; close.onclick = closeInspector;
  const body = el("div", "ibody");
  // 头部始终挂载，具体分支只负责填充内容
  head.append(h, close);
  box.append(head, body);

  if (spec.kind === "source") {
    const src = srcOf(spec.id);
    if (!src) { h.textContent = "来源不存在"; return box; }
    const prov = DATA.PROVIDERS[src.provider] || { label: src.provider, hue: "gray" };
    h.textContent = "来源详情";

    const identity = el("section");
    const t = el("h4"); t.textContent = "基础身份"; identity.append(t);
    const idCode = el("code", "uuid"); idCode.textContent = src.id;
    const urlNode = (() => {
      if (!src.canonical_url) return "无远端地址（本地材料）";
      const a = el("a"); a.href = src.canonical_url; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.textContent = src.demo_original_url || src.canonical_url; return a;
    })();
    identity.append(kv([
      ["标题", src.cached_title || "标题尚未取得"],
      ["来源种类", prov.label],
      ["资源类型", src.resource_type],
      ["所属项目", projOf(src.project_id).name],
      ["来源身份", idCode],
      ["规范地址", urlNode],
    ]));
    if (!src.canonical_url && src.check_error) {
      const n = el("p", "tiny muted"); n.style.marginTop = "8px";
      n.textContent = `读取失败：${src.check_error.message}（${fullTime(src.check_error.at)}）`;
      identity.append(n);
    }
    body.append(identity);

    // 远端检查
    const remote = el("section");
    const rt = el("h4"); rt.textContent = "远端检查"; remote.append(rt);
    if (!src.last_checked_at) {
      const p = el("p", "small muted");
      p.textContent = "尚未检查远端，因此不能说明是否已是最新。";
      remote.append(p);
    } else {
      const obs = src.remote_observation;
      const concl = obs && obs.conclusion;
      const hue = concl === "changed" ? "orange" : concl === "unchanged" ? "green" : "gray";
      remote.append(tag(src.check_error ? (concl === "changed" ? "上次发现更新 · 本次检查失败" : "本次检查失败") : concl === "changed" ? "远端有更新" : concl === "unchanged" ? "检查时远端未变化" : "缺少比较基线／无法确认", src.check_error ? "orange" : hue, true));
      const p = el("p", "small muted"); p.style.marginTop = "8px";
      p.textContent = src.check_error ? src.check_error.message : obs ? obs.detail : "未记录检测依据";
      remote.append(p);
      remote.append(kv([["检查时间", fullTime(src.last_checked_at)], ["检测方法", obs ? obs.method : "尚未记录"]]));
      const n = el("p", "tiny muted"); n.style.marginTop = "8px";
      n.textContent = "「最新已收录版本」不等于飞书当前最新版本；这里只显示已保存的检查结果。";
      remote.append(n);
    }
    if (src.canonical_url) body.append(remote);

    // 快照
    const vers = DATA.source_versions.filter((v) => v.source_id === src.id).sort((a, b) => b.version - a.version);
    const snaps = el("section");
    const st = el("h4"); st.textContent = `已保存快照 · ${vers.length} 版`; snaps.append(st);
    for (const v of vers) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const top = el("div");
      top.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;";
      top.append(tag("v" + v.version, src.provider === "feishu" ? "blue" : "gray"));
      if (v.id === (src.latest_snapshot_id)) top.append(tag("本地主快照", "green"));
      if (spec.sv === v.id) top.append(tag("正在查看", "indigo"));
      const at = el("span", "tiny muted"); at.textContent = "获取 " + fullTime(v.captured_at);
      top.append(at);
      g.append(top);
      const meta = el("div", "tiny muted"); meta.style.marginTop = "5px";
      meta.textContent = [
        v.capture_scope.mode === "selection" ? "节选：" + (v.capture_scope.note || "范围已记录") : "采集范围：全部",
        v.provider_revision ? "远端 revision " + v.provider_revision : "远端 revision 未取得",
      ].join(" · ");
      g.append(meta);
      row.append(g);
      row.append(chipBtn("查看", () => openInspector({ kind: "source", id: src.id, sv: v.id })));
      snaps.append(row);
    }
    body.append(snaps);

    // 正在查看的快照正文
    if (spec.sv) {
      const v = svOf(spec.sv);
      if (v) {
        const c = el("section");
        const ct = el("h4"); ct.textContent = `快照正文 · v${v.version}`; c.append(ct);
        if (v.body_text) {
          // markdown 快照按语义渲染；纯文本/转写按原样呈现，不做改写
          if (v.body_format === "markdown") {
            const md = el("div", "doc");
            md.style.fontSize = "13.5px";
            md.style.background = "var(--bg-grouped)";
            md.style.padding = "14px 16px";
            md.style.borderRadius = "var(--r-sm)";
            md.append(renderMarkdown(v.body_text));
            c.append(md);
            const n = el("p", "tiny muted"); n.style.marginTop = "7px";
            n.textContent = "按已保存的 Markdown 渲染；原件与定位信息一并保留。";
            c.append(n);
          } else {
            const pre = el("pre"); pre.textContent = v.body_text; c.append(pre);
          }
        } else {
          const p = el("p", "small muted");
          p.textContent = v.assets.some((a) => a.role === "original")
            ? "该快照只有附件，未提取正文。可打开附件查看。"
            : "该快照未保存正文。";
          c.append(p);
        }
        const assets = el("section");
        const at2 = el("h4"); at2.textContent = "文件"; assets.append(at2);
        const th = el("div", "thumbs");
        for (const a of v.assets) {
          const f = el("figure", "thumb");
          f.style.setProperty("--h", hueOf(prov.hue));
          const im = el("div", "img");
          im.textContent = a.mime_type.startsWith("image") ? "🖼" : a.mime_type.includes("pdf") ? "📄" : a.mime_type.startsWith("video") ? "🎬" : a.mime_type.includes("presentation") ? "📊" : "📎";
          if (a.url && a.availability === 'available') {
            if (/^image\/(png|jpeg|gif|webp|avif)$/.test(a.mime_type)) {
              const image = el('img'); image.src=a.url; image.alt=a.display_name; image.loading='lazy';
              image.style.cssText='width:100%;height:100%;object-fit:contain'; im.replaceChildren(image);
            } else if (/^(video|audio)\//.test(a.mime_type)) {
              const media = el(a.mime_type.startsWith('video')?'video':'audio'); media.src=a.url; media.controls=true; media.preload='metadata';
              media.style.width='100%'; im.replaceChildren(media);
            }
          }
          f.append(im);
          const cap = el("figcaption");
          cap.textContent = a.display_name;
          const sz = el("div", "tiny muted"); sz.textContent = (a.size_bytes / 1048576).toFixed(1) + " MB";
          cap.append(sz);
          if (a.url && a.availability === 'available') {
            const open = el('a','chipbtn'); open.href=a.url; open.target='_blank'; open.rel='noopener noreferrer'; open.textContent='打开文件'; cap.append(open);
          }
          if (['missing','unavailable','changed'].includes(a.availability)) {
            const state=el('div','tiny avail'); state.textContent=a.availability==='changed'?'文件内容已变化，不能作为此历史快照读取':'登记文件当前不可用'; cap.append(state);
          }
          addFileAction(cap, v, a);
          if (a.availability === "external_missing") {
            const w = el("div", "tiny avail"); w.textContent = "外部原件当前不可访问";
            cap.append(w);
          }
          f.append(cap);
          th.append(f);
        }
        assets.append(th);
        if (v.assets.some((a) => a.availability === "external_missing")) {
          const p = el("p", "tiny muted"); p.style.marginTop = "10px";
          p.textContent = "登记时保存的是外部路径，未复制副本。原件不可用时，来源与关联记录仍然保留。";
          assets.append(p);
        }
        body.append(c, assets);
      }
    }

    // 被谁使用
    const used = itemsUsingSourceVersion(spec.sv || src.latest_snapshot_id);
    const allUsed = DATA.source_versions
      .filter((v) => v.source_id === src.id)
      .flatMap((v) => itemsUsingSourceVersion(v.id));
    const dedup = [];
    const seen = new Set();
    for (const u of allUsed) { const k = u.object.id + "::" + u.item.item_id; if (!seen.has(k)) { seen.add(k); dedup.push(u); } }

    const useSec = el("section");
    const ut = el("h4"); ut.textContent = `引用此来源的 draft 条目 · ${dedup.length}`; useSec.append(ut);
    if (!dedup.length) {
      const p = el("p", "small muted");
      p.textContent = "尚未有对象引用该来源。材料仍已保存，未被引用不代表未读或出错。";
      useSec.append(p);
    }
    for (const u of dedup) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const k = el("div", "rel-k");
      k.textContent = (typeCode(u.object.type_key) || "") + " " + typeName(u.object.type_key);
      const v = el("div", "rel-v");
      v.textContent = u.item.data.topic || u.item.data.question || u.item.data.requirement || u.item.data.deliverable || u.item.item_id;
      g.append(k, v);
      const kind = el("div", "tiny muted"); kind.style.marginTop = "3px";
      kind.textContent = "证据关系：" + (DATA.EVIDENCE[u.evidence_kind] ? DATA.EVIDENCE[u.evidence_kind].label : u.evidence_kind);
      g.append(kind);
      row.append(g);
      row.append(chipBtn("前往", () => go(`#/p/${src.project_id}/draft/${u.object.id}`)));
      useSec.append(row);
    }
    body.append(useSec);
  }

  if (spec.kind === "object") {
    const o = oOf(spec.id);
    if (!o) { h.remove(); const t = el("h3"); t.textContent = "对象不存在"; head.prepend(t); return box; }
    const meta = typeMeta(o.type_key);
    const code = typeCode(o.type_key);
    const rev = headRev(o);
    const hue = typeHue(o.type_key);
    h.remove();
    const badge = el("span");
    badge.style.cssText = "display:flex;gap:7px;align-items:center;flex-wrap:wrap;flex:1;";
    if (code) badge.append(codeChip(code, themeOf(o.type_key) ? themeOf(o.type_key).hue : "gray"));
    const nm = el("span"); nm.style.fontWeight = "600"; nm.style.fontSize = "13.5px"; nm.textContent = typeName(o.type_key);
    badge.append(nm);
    const kind = el("span", "tiny muted"); kind.textContent = "对象说明"; badge.append(kind);
    head.prepend(badge);

    const sec = el("section");
    const t1 = el("h4"); t1.textContent = "这是什么"; sec.append(t1);
    const p1 = el("p", "small"); p1.textContent = meta ? meta.meaning : "尚未记录对象说明。";
    sec.append(p1);
    body.append(sec);

    if (meta) {
      const b = el("section");
      const t2 = el("h4"); t2.textContent = "归属边界"; b.append(t2);
      const p2 = el("p", "small"); p2.textContent = meta.boundary || "尚未记录。"; b.append(p2);
      body.append(b);
      const s2 = el("section");
      const t3 = el("h4"); t3.textContent = "可能来源"; s2.append(t3);
      const p3 = el("p", "small"); p3.textContent = meta.sources || "尚未记录。"; s2.append(p3);
      body.append(s2);
      const s3 = el("section");
      const t4 = el("h4"); t4.textContent = "用途与承接"; s3.append(t4);
      const p4 = el("p", "small"); p4.textContent = meta.usage || "尚未记录。"; s3.append(p4);
      body.append(s3);
      const s4 = el("section");
      const t5 = el("h4"); t5.textContent = "缺失或冲突的处理"; s4.append(t5);
      const p5 = el("p", "small"); p5.textContent = meta.missing || "尚未记录。"; s4.append(p5);
      body.append(s4);
    }

    const vs = el("section");
    const vt = el("h4"); vt.textContent = `版本 · ${revsOf(o.id).length} 版`; vs.append(vt);
    if (!revsOf(o.id).length) {
      const p = el("p", "small muted"); p.textContent = "该对象尚未建立内容，不显示为待完成任务。";
      vs.append(p);
    }
    for (const r of revsOf(o.id).slice().reverse()) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const top = el("div"); top.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;";
      top.append(tag("v" + r.version, hue === "var(--gray)" ? "gray" : "indigo"));
      if (r.id === o.current_revision_id) top.append(tag("当前版本", "green"));
      g.append(top);
      const ch = DATA.changes.find((c) => c.id === r.change_id);
      const m = el("div", "tiny muted"); m.style.marginTop = "4px";
      m.textContent = fullTime(r.created_at) + (ch ? " · " + ch.reason : "");
      g.append(m);
      row.append(g);
      const b = chipBtn("在正文中查看", () => { S.versionOf[o.id] = r.version; closeInspector(); });
      row.append(b);
      vs.append(row);
    }
    body.append(vs);

    const rel = el("section");
    const rt = el("h4"); rt.textContent = "关联"; rel.append(rt);
    const rs = relationsOf(o.id);
    const rb = el("div", "rel");
    if (!rs.up.length && !rs.down.length) {
      const p = el("p", "small muted"); p.textContent = "尚未建立依赖关系。";
      rb.append(p);
    }
    for (const u of rs.up) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const k = el("div", "rel-k"); k.textContent = "依赖 · " + (u.kind === "fact" ? "事实" : u.kind === "derivation" ? "推导" : "表达");
      const v = el("div", "rel-v");
      v.textContent = (u.object ? (typeCode(u.object.type_key) || "") + " " + typeName(u.object.type_key) : "未知对象") + " / " + u.item_id;
      g.append(k, v); row.append(g);
      rb.append(row);
    }
    for (const d of rs.down) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const k = el("div", "rel-k"); k.textContent = "被依赖";
      const v = el("div", "rel-v");
      v.textContent = (d.object ? (typeCode(d.object.type_key) || "") + " " + typeName(d.object.type_key) : "未知对象") + " / " + d.item_id;
      g.append(k, v); row.append(g);
      rb.append(row);
    }
    rel.append(rb);
    body.append(rel);
  }

  // 关闭与返回路径
  const foot = el("div");
  foot.style.cssText = "position:sticky;bottom:0;background:var(--bg-elevated);padding:12px 0 0;border-top:1px solid var(--separator);";
  foot.append(btn("关闭详情", closeInspector, "sm"));
  body.append(foot);

  return box;
}

/* ═══════════════════════════ 视图 ═════════════════════════════════════ */

/* ── 项目列表 ──────────────────────────────────────────────────────────── */
function viewProjects() {
  const c = el("div", "content wide projects-content");

  const active = DATA.projects.filter((p) => p.lifecycle === "active");
  const archived = DATA.projects.filter((p) => p.lifecycle === "archived");

  const group = (title, list) => {
    if (!list.length) return;
    const gh = el("div");
    gh.style.cssText = "display:flex;align-items:baseline;gap:10px;margin:30px 0 10px;";
    const h = el("h2"); h.style.cssText = "font-size:13px;font-weight:660;letter-spacing:.05em;text-transform:uppercase;color:var(--label-3);";
    h.textContent = title;
    gh.append(h);
    c.append(gh);

    const g = el("div", "listgroup");
    for (const p of list) {
      const row = el("div", "lrow clickable");
      row.onclick = () => go(`#/p/${p.id}/${p.working_scene}`);
      row.tabIndex = 0; row.setAttribute("role", "link");
      row.onkeydown = (e) => { if (e.target === row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); row.click(); } };
      const dot = el("span"); dot.style.cssText = `width:9px;height:9px;border-radius:50%;margin-top:7px;flex:none;background:${hueOf(themeHueForProject(p.id))};`;
      row.append(dot);
      const g2 = el("div", "grow");
      const h4 = el("h4"); h4.textContent = p.name; g2.append(h4);
      if (p.client_summary) { const s = el("div", "sub"); s.textContent = p.client_summary; g2.append(s); }
      const act = DATA.project_activity[p.id];
      const a = el("div", "sub");
      a.style.marginTop = "6px";
      if (act) {
        a.textContent = `最新更新：${act.summary}`;
      } else {
        a.textContent = "该项目尚无已保存内容。";
        a.style.color = "var(--label-3)";
      }
      g2.append(a);
      const monitors = el("div", "sub");
      monitors.textContent = projectMonitorSummary(DATA, p.id);
      g2.append(monitors);
      row.append(g2);
      const right = el("div");
      right.style.cssText = "text-align:right;flex:none;display:flex;flex-direction:column;gap:6px;align-items:flex-end;";
      const tm = el("div", "tiny muted"); tm.style.fontVariantNumeric = "tabular-nums";
      tm.textContent = `创建于 ${fullTime(p.created_at)}`;
      right.append(tm);
      const copyName = chipBtn("复制项目名称", () => {});
      copyName.onclick = (e) => { e.stopPropagation(); copyText(p.name, copyName); };
      right.append(copyName);
      row.append(right);
      g.append(row);
    }
    c.append(g);
  };

  if (!active.length && !archived.length) {
    c.append(empty("📁", "还没有项目", ["可以把下方的新建项目提示交给 Agent。"]));
  }
  group("当前项目", active);
  group("过往项目", archived);

  // 新建项目：只给可复制的意图，不在页面提交写入
  const nc = el("section", "card project-create-dock");
  nc.setAttribute("aria-label", "新建项目");
  const nh = el("header");
  const nh3 = el("h3"); nh3.textContent = "新建项目"; nh.append(nh3);
  const ng = el("span", "grow"); nh.append(ng);
  nh.append(tag("在 Codex 中创建", "blue"));
  nc.append(nh);
  const nb = el("div", "body");
  const np = el("p", "small muted");
  np.textContent = "复制到Agent会话框";
  nb.append(np);
  const intent = "用 Yu+ 新建一个项目，名称：______；客户/简述：______。建立后把 project_id 告诉我。";
  const box = el("div", "copyable");
  const codeEl = el("code"); codeEl.style.flex = "1"; codeEl.textContent = intent;
  box.append(codeEl);
  const cb = chipBtn("复制", () => {});
  cb.onclick = () => copyText(intent, cb);
  box.append(cb);
  nb.append(box);
  nc.append(nb);
  c.append(nc);

  return c;
}

// 给项目分配一个主题色，让列表有色彩识别度但不暗示状态
function themeHueForProject(pid) {
  const objs = DATA.objects.filter((o) => o.project_id === pid && o.layer === "draft" && o.current_revision_id);
  if (!objs.length) return "gray";
  const th = themeOf(objs[0].type_key);
  return th ? th.hue : "gray";
}

// Shared read-only monitor panel; all controls inspect data or copy a scoped intent.
function projectMonitorPanel(pid) {
  const monitors = projectMonitors(DATA, pid);
  const panel = el("section", "card");
  panel.style.marginTop = "20px";
  panel.setAttribute("aria-label", "监控群聊");
  const header = el("header");
  const title = el("h3", "grow"); title.textContent = "监控群聊";
  header.append(title, tag(projectMonitorSummary(DATA, pid), monitors.some(m => monitorSummary(m).attention) ? "orange" : "gray"));
  panel.append(header);
  const body = el("div", "body");
  if (!monitors.length) {
    const note = el("p", "small muted");
    note.textContent = "尚未绑定监控群聊。可在 Codex 中指定这个项目需要监控的飞书群。";
    body.append(note);
  }
  for (const monitor of monitors) {
    const summary = monitorSummary(monitor);
    const group = el("section");
    group.style.cssText = "padding:4px 0 16px;overflow-wrap:anywhere;";
    group.setAttribute("aria-label", monitor.chat_name || "群名尚未记录");
    const heading = el("div");
    heading.style.cssText = "display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px;";
    const name = el("h4");
    const url = safeChatUrl(monitor.chat_url);
    if (url) {
      const link = el("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer";
      link.textContent = monitor.chat_name || "打开群聊";
      link.title = "在新窗口打开飞书群聊";
      name.append(link);
    } else name.textContent = monitor.chat_name || "群名尚未记录";
    heading.append(name, tag(summary.status, monitor.status === "paused" ? "gray" : summary.attention ? "orange" : "green"));
    const interval = el("span", "small muted"); interval.textContent = summary.interval; heading.append(interval);
    group.append(heading);
    group.append(kv([
      ["历史收集", summary.history],
      ["已拉取至", fullTime(monitor.fetched_through)],
      ["最近检查", fullTime(monitor.last_checked_at)],
      ["最近同步完成", fullTime(monitor.last_completed_at)],
      ["最近保存结果", summary.result],
      ["待处理消息", summary.pending === null ? "尚未记录" : `${summary.pending} 条`],
      ...(Number.isInteger(monitor.clarification_count) && monitor.clarification_count >= 0 ? [["已记录澄清消息", `${monitor.clarification_count} 条`]] : []),
      ["定时任务", summary.schedule],
      ["调度核验", fullTime(monitor.schedule?.verified_at)],
      ["最近错误", summary.error || "无已记录错误"],
    ]));
    if (summary.overdue) {
      const note = el("p", "small muted"); note.style.marginTop = "10px";
      note.textContent = "按已保存的检查间隔，尚未收到本轮结果。";
      group.append(note);
    }
    const history = el("details"); history.style.marginTop = "12px";
    const label = el("summary", "small"); label.style.cursor = "pointer"; label.textContent = "查看已保存运行记录";
    history.append(label);
    const runs = monitorRuns(DATA, pid, monitor.id);
    if (!runs.length) {
      const note = el("p", "small muted"); note.textContent = "当前视图未提供运行明细；可复制查看记录提示交给 Agent。";
      history.append(note);
    }
    for (const run of runs) {
      const entry = el("div"); entry.style.marginTop = "12px";
      entry.append(kv([["运行编号", run.id], ["开始时间", fullTime(run.started_at || run.created_at)], ["完成时间", fullTime(run.completed_at)], ["已保存阶段", monitorRunStatus(run.status || run.phase)], ["结果", typeof run.summary === "string" ? run.summary : "尚无已保存结果"], ["错误", typeof run.error === "string" ? run.error : run.error?.message || "无已记录错误"]]));
      history.append(entry);
    }
    group.append(history);
    const actions = el("div"); actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;";
    for (const [action, label] of [["sync","复制立即同步 Prompt"],[monitor.status === "paused" ? "resume" : "pause",monitor.status === "paused" ? "复制恢复 Prompt" : "复制暂停 Prompt"],["interval","复制调整间隔 Prompt"],["remove","复制解除绑定 Prompt"],["inspect","复制查看记录 Prompt"]]) {
      let prompt;
      try { prompt = monitorPrompt(DATA, pid, monitor.id, action); } catch { continue; }
      const button = chipBtn(label, () => copyText(prompt, button));
      button.title = "复制到 Agent 会话后执行；复制本身不会更改监控";
      button.setAttribute("aria-live", "polite");
      actions.append(button);
    }
    group.append(actions);
    body.append(group);
  }
  if (monitors.length) {
    const note = el("p", "tiny muted");
    note.textContent = "仅显示已保存的检查与同步结果。历史范围限于当前飞书身份可访问的消息；历史收集完成不等于全部消息已处理。复制 Prompt 不会执行操作。";
    body.append(note);
  }
  panel.append(body);
  return panel;
}

/* ── 项目内：draft ─────────────────────────────────────────────────────── */
function viewDraft(pid) {
  const c = el("div", "content wide");
  const objs = DATA.objects.filter((o) => o.project_id === pid && o.layer === "draft" && o.type_key !== "expression_guide");

  const head = el("div");
  head.style.margin = "30px 0 6px";
  const h = el("h1", "largetitle");
  h.id = "draft-title";
  h.style.margin = "0 0 6px";
  h.textContent = "信息收集";
  head.append(h);
  c.append(head);
  c.append(projectMonitorPanel(pid));

  const body = el("div");
  body.style.marginTop = "20px";
  c.append(body);

  const selectedId = S.route.objId;
  const layout = el("div");
  layout.className = "object-layout draft-layout";
  layout.classList.toggle("directory-collapsed", S.directoryCollapsed);

  /* 目录：按阅读主题分组 */
  const nav = el("div", "card draft-directory");
  let directoryPreview = false;
  let suppressHover = false;
  let leaveTimer;
  const directoryOpen = () => !S.directoryCollapsed || directoryPreview;
  function updateDirectoryState() {
    layout.classList.toggle("directory-collapsed", S.directoryCollapsed);
    layout.classList.toggle("directory-preview", directoryPreview);
    updateDirectoryToggle();
  }
  function closeDirectoryPreview() {
    if (!directoryPreview) return Promise.resolve();
    suppressHover = true;
    directoryPreview = false;
    updateDirectoryState();
    return Promise.resolve();
  }
  nav.onpointerenter = event => {
    clearTimeout(leaveTimer);
    if (event.pointerType !== "mouse" || suppressHover || directoryOpen()) return;
    directoryPreview = true;
    updateDirectoryState();
  };
  nav.onpointerleave = () => {
    suppressHover = false;
    leaveTimer = setTimeout(() => {
      if (nav.isConnected && directoryPreview) closeDirectoryPreview().then(() => { suppressHover = false; });
    }, 140);
  };
  const navh = el("header");
  const nh = el("h3"); nh.textContent = "对象目录"; navh.append(nh);
  const ng = el("span", "grow"); navh.append(ng);
  const toggle = chipBtn(S.showAllTypes ? "只看有内容" : `全部 ${DATA.catalog.length} 类`, () => { S.showAllTypes = !S.showAllTypes; render(); });
  const switchIcon = el("span", "switch-icon"); switchIcon.textContent = "⇄";
  switchIcon.setAttribute("aria-hidden", "true"); toggle.prepend(switchIcon);
  toggle.title = "切换全部对象与已有内容";
  toggle.setAttribute("aria-pressed", String(S.showAllTypes));
  navh.append(toggle);
  const collapse = chipBtn("", () => {
    clearTimeout(leaveTimer);
    suppressHover = true;
    animatePanelToggle(layout, nav, () => {
      S.directoryCollapsed = !S.directoryCollapsed;
      directoryPreview = false;
      updateDirectoryState();
    });
  });
  collapse.classList.add("directory-toggle");
  function updateDirectoryToggle() {
    const label = directoryPreview ? "固定展开对象目录" : S.directoryCollapsed ? "展开对象目录" : "收起对象目录";
    collapse.setAttribute("aria-expanded", String(directoryOpen()));
    collapse.setAttribute("aria-label", label);
    collapse.title = label;
    setPanelToggleIcon(collapse, S.directoryCollapsed);
  }
  updateDirectoryToggle();
  collapse.setAttribute("aria-controls", "draftDirectoryList");
  navh.append(collapse);
  nav.append(navh);
  const navb = el("div", "body");
  navb.style.padding = "16px";

  const objnav = el("div", "objnav"); objnav.id = "draftDirectoryList";
  const visibleObjects = [];
  for (const th of DATA.THEMES) {
    let list = S.showAllTypes
      ? DATA.catalog.filter(m => th.types.includes(m.type_key)).map(m => objs.find(o => o.type_key === m.type_key) || { id: null, type_key: m.type_key, current_revision_id: null })
      : objs.filter((o) => th.types.includes(o.type_key));
    if (!S.showAllTypes) list = list.filter((o) => o.current_revision_id || o.id === selectedId);
    if (!list.length) continue;
    list.sort((a, b) => (typeCode(a.type_key) || "").localeCompare(typeCode(b.type_key) || ""));

    const g = el("div", "objgroup");
    const gh = el("div", "ghead");
    const gd = el("span"); gd.style.cssText = `width:8px;height:8px;border-radius:50%;background:${hueOf(th.hue)};`;
    gh.append(gd);
    const gt = el("h4"); gt.textContent = th.name; gh.append(gt);
    const gl = el("span", "line"); gh.append(gl);
    const gn = el("span", "n"); gn.textContent = list.length + " / " + th.types.length; gh.append(gn);
    g.append(gh);

    const ol = el("div", "objlist");
    for (const o of list) {
      visibleObjects.push(o);
      const key = o.id || o.type_key;
      const rev = headRev(o);
      const b = el("button", "objbtn" + (o.current_revision_id ? "" : " empty-obj"));
      b.type = "button";
      b.style.setProperty("--h", hueOf(th.hue));
      if (o.id === selectedId) b.setAttribute("aria-current", "true");
      const cc = el("span", "ct"); cc.textContent = typeCode(o.type_key) || "—";
      cc.style.color = hueOf(th.hue);
      cc.style.fontFamily = "var(--mono)";
      cc.style.fontWeight = "700";
      cc.style.fontSize = "11px";
      b.append(cc);
      const nm = el("span", "nm"); nm.textContent = typeName(o.type_key); b.append(nm);
      const ct = el("span", "ct");
      ct.textContent = rev ? (rev.payload.items ? rev.payload.items.length : 0) + " 条" : "无内容";
      b.append(ct);
      b.dataset.draftTarget = key;
      b.setAttribute("aria-controls", "draft-object-" + key);
      b.onclick = async () => {
        if (o.id) {
          history.pushState(null, "", `#/p/${pid}/draft/${o.id}`);
          S.route = parseRoute();
        }
        if (directoryPreview) {
          clearTimeout(leaveTimer);
          collapse.focus({ preventScroll: true });
          await closeDirectoryPreview();
        }
        if (layout.isConnected) scrollToDraft(key);
      };
      ol.append(b);
    }
    g.append(ol);
    objnav.append(g);
  }
  if (!objnav.children.length) objnav.append(empty("🗂", "还没有对象内容", [`可切换查看全部 ${DATA.catalog.length} 类对象。`]));
  navb.append(objnav);
  nav.append(navb);
  const directorySlot = el("div", "draft-directory-slot");
  directorySlot.append(nav);
  layout.append(directorySlot);

  /* 所有可见对象按目录顺序连续阅读；目录导航与版本切换不重建整页。 */
  const main = el("div", "draft-stream");
  for (const o of visibleObjects) {
    const section = el("section", "draft-section");
    const key = o.id || o.type_key;
    section.id = "draft-object-" + key;
    section.dataset.draftObject = key;
    section.setAttribute("aria-label", `${typeCode(o.type_key)} ${typeName(o.type_key)}`);
    if (o.id) section.append(objectBody(o, pid));
    else {
      const card = el("div", "card");
      const header = el("header");
      header.append(codeChip(typeCode(o.type_key), (themeOf(o.type_key) || {}).hue));
      const title = el("h3"); title.textContent = typeName(o.type_key); header.append(title);
      card.append(header, empty("○", "这个对象还没有内容", ["可以继续浏览其他对象，或让 Agent 收集相关材料。"]));
      section.append(card);
    }
    main.append(section);
  }
  if (!visibleObjects.length) main.append(empty("📄", "这个项目还没有已保存的对象内容",
    [`可以把材料交给 Agent，或切换到全部 ${DATA.catalog.length} 类查看对象。`]));
  layout.append(main);

  body.append(layout);
  return c;
}

// Animate measured sizes so both side-by-side and stacked directories transition smoothly.
const panelTransitions = new WeakMap();
function animatePanelToggle(layout, directory, changeState) {
  let anchor = draftReadingAnchor();
  const before = directory.getBoundingClientRect();
  const beforeGrid = getComputedStyle(layout).gridTemplateColumns;
  const beforeGap = getComputedStyle(layout).columnGap;
  const beforeRowGap = getComputedStyle(layout).rowGap;
  const dock = layout === document.body ? document.querySelector(".project-create-dock") : null;
  const dockLeft = dock?.getBoundingClientRect().left;
  panelTransitions.get(layout)?.();
  changeState();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    restoreDraftAnchor(anchor);
    return Promise.resolve();
  }
  const after = directory.getBoundingClientRect();
  const timing = { duration: 260, easing: "cubic-bezier(.22, 1, .36, 1)" };
  const animations = [
    layout.animate({
      gridTemplateColumns: [beforeGrid, getComputedStyle(layout).gridTemplateColumns],
      columnGap: [beforeGap, getComputedStyle(layout).columnGap],
      rowGap: [beforeRowGap, getComputedStyle(layout).rowGap],
    }, timing),
    directory.animate({ width: [before.width + "px", after.width + "px"], height: [before.height + "px", after.height + "px"] }, timing),
  ];
  if (dock) animations.push(dock.animate({ left: [dockLeft + "px", dock.getBoundingClientRect().left + "px"] }, timing));
  const content = directory.querySelector(".body");
  if (content && getComputedStyle(content).display !== "none") animations.push(content.animate(
    { opacity: [0, 1], transform: ["translateX(-6px)", "translateX(0)"] },
    { duration: 180, delay: 60, fill: "backwards", easing: "ease-out" },
  ));
  directory.style.overflow = "hidden";
  const input = new AbortController();
  for (const event of ["wheel", "touchstart", "keydown"]) window.addEventListener(event, () => { anchor = null; }, { passive: true, signal: input.signal });
  let frame;
  const keepPosition = () => {
    if (!layout.isConnected) { cleanup(); return; }
    restoreDraftAnchor(anchor);
    frame = requestAnimationFrame(keepPosition);
  };
  const cleanup = () => {
    cancelAnimationFrame(frame);
    input.abort();
    animations.forEach(animation => animation.cancel());
    directory.style.overflow = "";
    panelTransitions.delete(layout);
  };
  panelTransitions.set(layout, cleanup);
  keepPosition();
  return Promise.all(animations.map(animation => animation.finished)).then(() => {
    if (panelTransitions.get(layout) !== cleanup) return;
    cleanup();
    restoreDraftAnchor(anchor);
    updateDraftDirectory();
  }).catch(() => {}); // A second click replaces the in-flight transition from its current size.
}

// Directory navigation never rebuilds the document. Scroll tracking only updates navigation state.
function draftReadingLine() {
  const directory = document.querySelector(".directory-preview .draft-directory-slot") || document.querySelector(".draft-directory");
  const stream = document.querySelector(".draft-stream");
  if (directory && stream && Math.abs(directory.getBoundingClientRect().left - stream.getBoundingClientRect().left) < 10)
    return Math.max(100, directory.getBoundingClientRect().bottom + 12);
  return 100;
}
function draftReadingAnchor() {
  // At the top of the reader, let a stacked directory push content downward.
  // Anchoring a card below it would scroll the visible page title out of view.
  const title = $("draft-title");
  const toolbarBottom = $("toolbar")?.getBoundingClientRect().bottom || 0;
  if (title && title.getBoundingClientRect().bottom > toolbarBottom)
    return { id: title.id, top: title.getBoundingClientRect().top };
  const line = draftReadingLine();
  const sections = [...document.querySelectorAll(".draft-section")];
  const section = sections.find(s => s.getBoundingClientRect().bottom > line);
  if (!section) return null;
  return { id: section.id, top: section.getBoundingClientRect().top };
}
function restoreDraftAnchor(anchor) {
  const section = anchor && $(anchor.id);
  if (section) window.scrollBy(0, section.getBoundingClientRect().top - anchor.top);
}
function refreshDraftObject(o, pid) {
  const section = $("draft-object-" + o.id);
  if (!section) { render(); return; }
  const top = section.getBoundingClientRect().top;
  section.replaceChildren(objectBody(o, pid));
  highlightMoney(section);
  initProseToggles();
  window.scrollBy(0, section.getBoundingClientRect().top - top);
}
function scrollToDraft(key) {
  const section = $("draft-object-" + key);
  if (!section) return;
  section.scrollIntoView({ block: "start", behavior: "instant" });
  updateDraftDirectory();
}
let draftScrollFrame = 0;
function updateDraftDirectory() {
  draftScrollFrame = 0;
  const sections = [...document.querySelectorAll(".draft-section")];
  if (!sections.length) return;
  const readingLine = draftReadingLine() + 10;
  const active = sections.find(s => s.getBoundingClientRect().bottom > readingLine) || sections.at(-1);
  for (const button of document.querySelectorAll("[data-draft-target]")) {
    if (button.dataset.draftTarget === active.dataset.draftObject) button.setAttribute("aria-current", "true");
    else button.removeAttribute("aria-current");
  }
}
window.addEventListener("scroll", () => {
  if (!draftScrollFrame && S.route?.view === "draft") draftScrollFrame = requestAnimationFrame(updateDraftDirectory);
}, { passive: true });

/* 单个 draft 对象的正文 */
function objectBody(o, pid) {
  const wrap = el("div");
  const meta = typeMeta(o.type_key);
  const hue = typeHue(o.type_key);
  const current = headRev(o);
  const rev = revsOf(o.id).find(r => r.version === S.versionOf[o.id]) || current;
  const isOld = rev && current && rev.id !== current.id;
  const code = typeCode(o.type_key);

  const card = el("div", "card");
  const head = el("header");
  head.style.padding = "18px 22px";
  if (code) head.append(codeChip(code, (themeOf(o.type_key) || {}).hue || "gray"));
  const titleGroup = el("div", "object-title");
  const h = el("h3"); h.style.fontSize = "19px"; h.textContent = typeName(o.type_key);
  const help = el("button", "object-help");
  help.type = "button"; help.textContent = "?";
  help.setAttribute("aria-label", "对象说明");
  help.title = "查看对象说明";
  help.onclick = () => openInspector({ kind: "object", id: o.id });
  titleGroup.append(h, help); head.append(titleGroup);
  const grow = el("span", "grow"); head.append(grow);

  if (rev) {
    head.append(versionControl(o, rev, current, pid));
  } else {
    head.append(tag("尚未建立内容", "gray"));
  }
  head.append(copyRefButton({
    project_name: projOf(pid).name, project_id: pid,
    object_label: (code ? code + " " : "") + typeName(o.type_key) + `（${o.id}）`,
    version_label: rev ? "v" + rev.version + "（" + rev.id + "）" : "尚未建立内容",
  }));
  card.append(head);

  const bd = el("div", "body");
  bd.style.padding = "22px";
  bd.classList.add("draft-object-content");

  if (!rev) {
    bd.append(empty("○", "这个对象还没有内容",
      ["没有内容不代表故障，也不要求补齐才能继续。可以在 Codex 中让 Agent 从材料里整理，或暂时跳过。"]));
    const rel = relationsOf(o.id);
    if (rel.up.length || rel.down.length) {
      const l = el("div", "small muted");
      l.textContent = "已有其他对象引用它的位置：" + [...rel.down].map((d) => typeName(d.object.type_key)).join("、");
      bd.append(l);
    }
    card.append(bd);
    wrap.append(card);
    return wrap;
  }

  const metaLine = el("div", "tiny muted");
  metaLine.style.marginBottom = "18px";
  metaLine.textContent = `v${rev.version} · 更新于 ${fullTime(rev.created_at)}`;
  bd.append(metaLine);

  if (isOld) {
    bd.append(banner("orange", "◷", [
      Object.assign(el("p"), { textContent: `正在阅读历史 v${rev.version}，当前版本为 v${current.version}。` }),
      chipBtn("回到当前版本", () => { delete S.versionOf[o.id]; refreshDraftObject(o, pid); }),
    ]));
  }
  const itemsBox = el("div", "items");
  const order = (rev.payload.item_order && rev.payload.item_order.length ? rev.payload.item_order : rev.payload.items.map((i) => i.item_id));
  for (const iid of order) {
    const it = rev.payload.items.find((x) => x.item_id === iid);
    if (!it) continue;
    if (o.type_key !== "milestones") itemsBox.append(itemCard(o, rev, it, hue));
  }
  if (o.type_key === "milestones") bd.append(milestoneChart(o, rev, hue));
  else {
    if (o.type_key === "deliverables") bd.append(deliveryTimeline(o, rev));
    bd.append(itemsBox);
  }
  card.append(bd);
  wrap.append(card);

  return wrap;
}

function versionControl(o, rev, current, pid) {
  const area = el("div", "version-control");
  const label = el("span"); label.textContent = "版本";
  const trigger = chipBtn("", () => {
    if (menu.matches(":popover-open")) { menu.hidePopover(); return; }
    const rect = trigger.getBoundingClientRect();
    menu.style.left = Math.max(12, Math.min(rect.right - 240, innerWidth - 252)) + "px";
    const height = Math.min(320, options.length * 64 + 14);
    menu.style.top = (rect.bottom + height + 8 <= innerHeight ? rect.bottom + 8 : Math.max(12, rect.top - height - 8)) + "px";
    menu.showPopover();
    options.find((b) => b.getAttribute("aria-checked") === "true")?.focus({ preventScroll:true });
  });
  trigger.id = "draftVersion-" + o.id;
  trigger.classList.add("version-trigger");
  trigger.setAttribute("aria-label", "历史版本");
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  const value = el("span"); value.textContent = (rev.id === current.id ? "当前 v" : "历史 v") + rev.version;
  const chevron = el("span", "version-chevron"); chevron.textContent = "⌄"; chevron.setAttribute("aria-hidden", "true");
  trigger.append(value, chevron);
  const menu = el("div", "version-menu");
  menu.id = "versions-" + o.id; menu.setAttribute("popover", "auto");
  menu.setAttribute("role", "menu"); menu.setAttribute("aria-label", "选择版本");
  trigger.setAttribute("aria-controls", menu.id);
  const options = [];
  for (const version of revsOf(o.id).slice().reverse()) {
    const option = btn("", () => {
      menu.hidePopover();
      if (version.id === current.id) delete S.versionOf[o.id];
      else S.versionOf[o.id] = version.version;
      refreshDraftObject(o, pid);
      $(trigger.id)?.focus({ preventScroll: true });
    }, "version-option");
    option.setAttribute("role", "menuitemradio");
    option.setAttribute("aria-checked", String(version.id === rev.id));
    option.tabIndex = -1;
    const text = el("span");
    const title = el("b"); title.textContent = (version.id === current.id ? "当前版本 v" : "历史版本 v") + version.version;
    const time = el("small"); time.textContent = fullTime(version.created_at);
    text.append(title, time);
    const check = el("span", "version-check"); check.textContent = version.id === rev.id ? "✓" : ""; check.setAttribute("aria-hidden", "true");
    option.append(text, check); menu.append(option); options.push(option);
  }
  menu.addEventListener("toggle", () => trigger.setAttribute("aria-expanded", String(menu.matches(":popover-open"))));
  menu.onkeydown = (e) => {
    const index = options.indexOf(document.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      const next = e.key === "Home" ? 0 : e.key === "End" ? options.length - 1 : (index + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options[next].focus();
    } else if (e.key === "Escape" || e.key === "Tab") {
      menu.hidePopover(); trigger.focus({ preventScroll:true });
      if (e.key === "Escape") e.preventDefault();
    }
  };
  trigger.onkeydown = (e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); trigger.click(); } };
  area.append(label, trigger, menu);
  return area;
}

function resourceScope(o, it) {
  const box = el("section", "resource-scope");
  const title = el("h4"); title.textContent = "职责与Scope"; box.append(title);
  const responsibilities = DATA.objects.filter((x) => x.project_id === o.project_id && x.type_key === "responsibilities");
  const assignments = responsibilities.flatMap((x) => (headRev(x)?.payload.items || []).filter((r) =>
    r.dependencies?.some((dep) => dep.producer_object_id === o.id && dep.producer_item_id === it.item_id)));
  if (it.data.scope) { const p = el("p"); p.textContent = it.data.scope; box.append(p); }
  else if (!assignments.length) { const p = el("p", "muted"); p.textContent = "尚未记录职责与工作范围"; box.append(p); }
  for (const assignment of assignments) {
    const p = el("p"); p.textContent = (assignment.data.responsibility || assignment.data.duty); box.append(p);
    const note = el("p", "tiny muted");
    note.textContent = [DATA.EPISTEMIC[assignment.epistemic_kind]?.label, assignment.data.note].filter(Boolean).join(" · ");
    box.append(note);
  }
  return box;
}

function milestoneChart(o, rev, hue) {
  const box = el("div", "milestone-chart");
  const dated = rev.payload.items.filter((it) => { const d = milestoneDates(it); return Number.isFinite(d.from) && d.to >= d.from; })
    .sort((a,b) => milestoneDates(a).from - milestoneDates(b).from);
  if (dated.length) {
    const scale = timelineScale(dated.map(milestoneDates));
    const { min, max } = scale;
    const percent = (n) => (n - min) / (max - min) * 100;
    const legend = el("p", "tiny muted"); legend.textContent = `${scale.first} — ${scale.last}　· ◆ 时间节点　━ 时间区间`; box.append(legend);
    const scroll = el("div", "gantt-scroll"); const chart = el("div", "gantt-grid");
    const axis = el("div", "gantt-axis"); const axisLabel = el("span"); axisLabel.textContent = "节点 / 区间";
    const ticks = el("div", "gantt-ticks" + (scale.minuteScale ? " has-time" : ""));
    const tickPositions = [];
    for (const entry of scale.ticks) {
      const tick = el("span"); tick.textContent = entry.label; tick.title = entry.title;
      const position = percent(entry.value);
      tickPositions.push(position);
      tick.style.left = position + "%"; ticks.append(tick);
    }
    axis.append(axisLabel, ticks); chart.append(axis);
    for (const it of dated) {
      const dates = milestoneDates(it); const row = el("div", "gantt-row");
      const label = el("div", "gantt-label");
      const name = el("b"); name.textContent = it.data.event;
      const date = el("small"); date.textContent = dates.start === dates.end ? dates.start : `${dates.start} — ${dates.end}`;
      label.append(name, date);
      const track = el("div", "gantt-track");
      for (const position of tickPositions) { const line = el("span", "gantt-gridline"); line.style.left = position + "%"; track.append(line); }
      const mark = chipBtn("", () => { details.hidden = !details.hidden; mark.setAttribute("aria-expanded", String(!details.hidden)); });
      mark.className = "gantt-mark" + (dates.start === dates.end ? " is-point" : "");
      mark.style.setProperty("--h", hue);
      mark.style.left = percent(dates.from) + "%";
      if (dates.start !== dates.end) mark.style.width = Math.max(1, percent(dates.to)-percent(dates.from)) + "%";
      mark.setAttribute("aria-label", it.data.event + "，" + date.textContent + "，查看详情");
      mark.setAttribute("aria-expanded", "false"); mark.title = it.data.source_note || it.data.basis || it.data.event;
      const details = el("div", "gantt-details"); details.id = `milestone-${o.id}-${it.item_id}`; details.hidden = true;
      mark.setAttribute("aria-controls", details.id);
      details.append(itemCard(o, rev, it, hue));
      track.append(mark); row.append(label, track); chart.append(row, details);
    }
    scroll.append(chart); box.append(scroll);
  }
  for (const it of rev.payload.items.filter((it) => !dated.includes(it))) {
    const note = el("div", "timeline-note");
    const title = el("b"); title.textContent = it.data.event || "补充说明";
    const p = el("p"); p.textContent = it.data.text || it.data.note || "日期待明确";
    note.append(title, p, sourceLinksOf(it));
    addSourceTypePopover(note, it.epistemic_kind, `source-type-${rev.id}-${it.item_id}`);
    box.append(note);
  }
  return box;
}

function deliveryTimeline(o, rev) {
  const box = el("section", "delivery-timeline");
  const title = el("h4"); title.textContent = "交付时间线"; box.append(title);
  const milestones = DATA.objects.find((x) => x.project_id === o.project_id && x.type_key === "milestones");
  const dates = rev.id === o.current_revision_id ? (headRev(milestones)?.payload.items || []) : [];
  const rounds = [...new Set(rev.payload.items.filter((it) => it.data.deliverable).map((it) => it.data.round_key || "待安排"))].sort((a,b) => a.localeCompare(b, undefined, {numeric:true}));
  const list = el("ol");
  for (const round of rounds) {
    const row = el("li");
    const heading = el("h5"); heading.textContent = /^r\d+$/.test(round) ? `第 ${round.slice(1)} 轮` : round; row.append(heading);
    for (const it of rev.payload.items.filter((it) => it.data.deliverable && (it.data.round_key || "待安排") === round)) {
      const d = it.data; const entry = el("div", "delivery-entry");
      const name = el("b"); name.textContent = `${d.deliverable} · ${d.granularity || "交付内容待明确"}`;
      // Date references are suggestions from D09, never asserted as committed delivery deadlines.
      const match = dates.find((m) => d.granularity && m.data.event?.includes(d.granularity) && Number.isFinite(milestoneDates(m).from));
      const time = el("p", "small");
      if (d.date) time.textContent = parseScheduleTime(d.date)?.label || d.date;
      else if (match) {
        const span = milestoneDates(match);
        time.textContent = `参考：${span.start}${span.end !== span.start ? " — " + span.end : ""} · ${DATA.EPISTEMIC[match.epistemic_kind]?.label || "时间节点"}`;
      } else time.textContent = "交付日期待定";
      const summary = el("p", "tiny muted"); summary.textContent = [d.spec, d.note, match?.data.source_note || match?.data.basis].filter(Boolean).join(" · ");
      entry.append(name, time, summary); row.append(entry);
    }
    list.append(row);
  }
  box.append(list); return box;
}

/* 单条 draft 条目 */
function itemCard(o, rev, it, hue) {
  const d = el("div", "item");
  d.style.setProperty("--h", hue);

  const head = el("div", "ihead");
  const t = el("span", "topic");
  t.textContent = itemLabel(it, o.type_key);
  head.append(t);
  const g = el("span", "grow"); head.append(g);

  // 适用范围（局部要求不得显示成全项目要求）
  if (it.data.applies_to) head.append(tag(it.data.applies_to, "orange"));
  if (it.data.round_key) head.append(tag("轮次 " + it.data.round_key, "teal"));
  if (o.type_key === "open_questions") {
    const state = openQuestionState(it.data.status);
    head.append(tag(state.label, state.hue));
  }
  if (it.data.status) {
    const sm = { confirmed: ["已确认参与", "green"], candidate: ["候选", "gray"], pending: ["待确认", "orange"] }[it.data.status];
    if (sm) head.append(tag(sm[0], sm[1]));
  }
  head.append(copyRefButton({
    project_name: projOf(o.project_id).name, project_id: o.project_id,
    object_label: (typeCode(o.type_key) || "") + " " + typeName(o.type_key) + `（${o.id}）`,
    item_label: it.item_id + " · " + (it.data.topic || it.data.question || it.data.deliverable || ""),
    version_label: "v" + rev.version + "（" + rev.id + "）",
  }));
  d.append(head);

  // 按类型呈现：结构化字段 / 正文 / 清单
  const dd = it.data;
  const moneyKeys = new Set(["min_minor", "max_minor", "amount_minor"]);
  const skip = new Set(["topic", "question", "text", "note", "basis", "applies_to", "status", "captures", "time_kind"]);
  const fields = Object.keys(dd).filter((k) => !skip.has(k) && dd[k] !== null && dd[k] !== undefined && dd[k] !== "");
  const plainValue = ["venue", "brand_assets", "cooperation_type"].includes(o.type_key);
  const isQa = o.type_key === "qa";
  const proseLike = isQa
    ? (dd.answer || (dd.status === "不适用" ? ["不适用", dd.note].filter(Boolean).join("。") : "待答复"))
    : dd.text || dd.requirement || dd.risk || dd.answer || (plainValue && dd.value);

  if (proseLike) {
    const p = el("div", "prose");
    p.textContent = (isQa ? "回答：" : "") + proseLike;
    if (isQa && !dd.answer) p.classList.add("muted");
    d.append(p);
  }

  const rest = fields.filter((k) => !["text", "requirement", "risk", "answer", "answer_basis"].includes(k) && !(plainValue && k === "value"));
  if (rest.length) {
    const dl = el("dl", "field");
    dl.style.marginTop = proseLike ? "12px" : "0";
    for (const k of rest) {
      let v = dd[k];
      let isMoney = false;
      if (moneyKeys.has(k)) { const m = money(v, dd.currency); if (m) { v = m; isMoney = true; } }
      if (k === "currency" && fields.some(field => moneyKeys.has(field))) continue;
      if (k === "participation") v = ({candidate:"候选",verified_available:"已核实可用",confirmed:"已确认参与"})[v] || v;
      if (o.type_key === "milestones" && ["date", "start", "end"].includes(k)) v = parseScheduleTime(v)?.label || v;
      if (k === "resource_item_id") {
        const resourceObject=DATA.objects.find(x=>x.project_id===o.project_id && x.type_key==='resources');
        const resource=headRev(resourceObject)?.payload.items?.find(x=>x.item_id===v);
        v=resource?.data.name || v;
      }
      if (k === "related_object_ids" && Array.isArray(v)) v = v.map((id) => { const related = oOf(id); return related ? typeName(related.type_key) : "未找到关联对象"; });
      if (Array.isArray(v)) v = v.join("、");
      if (typeof v === "object") v = JSON.stringify(v);
      const dt = el("dt"); dt.textContent = FIELD_LABEL[k] || k; dl.append(dt);
      const dv = el("dd");
      if (isMoney) dv.className = "money";
      dv.textContent = String(v);
      if (k === "budget_kind") {
        dv.replaceChildren();
        dv.append(dd.budget_kind === "adopted"
          ? tag("本轮采用口径", "indigo", true)
          : tag(dd.budget_kind === "desired" ? "期望预算" : "客户原始说法", "blue", true));
      }
      dl.append(dv);
    }
    d.append(dl);
  }

  // 采用决定的依据
  if (it.epistemic_kind === "adopted_decision" && dd.decided_by) {
    const n = el("p", "tiny"); n.style.marginTop = "10px";
    n.textContent = `决定者：${dd.decided_by}` + (dd.rationale ? ` · 理由：${dd.rationale}` : "");
    n.style.color = "var(--indigo)";
    d.append(n);
  }

  if (o.type_key === "resources" && (dd.participation === "confirmed" || dd.status === "confirmed")) d.append(resourceScope(o, it));

  const footer = el("div", "item-footer");
  const sources = el("div", "item-sources");
  sources.append(sourceLinksOf(it));

  // 未知 / 分歧的显式表达
  if (it.epistemic_kind === "hypothesis") {
    const n = el("p", "tiny muted"); n.style.marginTop = "8px";
    n.textContent = "此条是假设/未核实信息，不是事实依据。";
    sources.append(n);
  }
  if (sources.textContent.trim()) { footer.append(sources); d.append(footer); }
  addSourceTypePopover(d, it.epistemic_kind, `source-type-${rev.id}-${it.item_id}`);
  return d;
}

/* 条目标题：优先使用条目自带的主题，否则按对象类型给出可读名称 */
function itemLabel(it, type_key) {
  const d = it.data || {};
  if (d.question) return "问题：" + d.question;
  if (d.topic) return d.topic;
  if (type_key === "audience") return d.audience || d.kind || "受众说明";
  if (d.deliverable) return d.deliverable + (d.round_key ? " · 轮次 " + d.round_key : "");
  if (d.meeting_name) return d.meeting_name;
  if (d.meeting) return d.meeting;
  if (d.event) return d.event;
  if (d.person_or_role) return d.person_or_role;
  if (d.role) return d.role + (d.who ? " · " + d.who : "");
  if (d.risk) return d.risk;
  if (d.name) return d.name;
  if (d.requirement) return d.requirement.length > 34 ? d.requirement.slice(0, 34) + "…" : d.requirement;
  if (d.statement) return d.statement;
  const byType = {
    budget_range: d.budget_kind === "adopted" ? "本轮采用预算" : "客户预算口径",
    budget_allocation: "预算分配",
    cooperation_type: "合作方式",
    client_brief: "需求条目",
    brand_assets: "品牌资料",
    deliverables: "交付条目",
  };
  if (byType[type_key]) return byType[type_key];
  return typeName(type_key);
}

const FIELD_LABEL = {
  background:'背景', why_now:'当前契机', goal:'目标', core_problem:'核心问题', decision_standard:'决策标准', preference:'偏好',
  category:'类别', condition:'条件', measurements:'尺寸与测量', asset_use:'资产使用条件', audience_kind:'受众类型', profile:'受众描述', needs:'需求', touchpoints:'触达点',
  area:'分配方向', priority:'投入重点', amount_minor:'分配金额', allocation_kind:'分配性质', restraint:'克制项', review_opinion:'审查意见', timezone:'时区', review_focus:'Review 关注内容',
  person_or_role:'人员 / 角色', boundary:'边界', requires_confirmation:'待确认事项', competitor:'竞争对象', public_work:'公开作品', finding:'判断与发现', difference:'差异',
  meeting_name:'会议', meeting_date:'会议日期', statement_kind:'陈述性质', follow_up_person:'跟进人', dimension:'评估维度', recommendation:'建议', strategy:'策略', research_finding:'研究发现', candidate:'方向候选', selection_reason:'取舍理由',
  resource_item_id:'关联资源', specifications:'格式规格', exclusions:'不做范围', usage_limits:'使用限制', capabilities:'能力', portfolio:'作品依据', conditions:'参与条件', responsibility:'职责', interfaces:'协作接口', acceptance:'承接情况', needs_verification:'待核实', disposition:'处理决定', conclusion:'结论', action_items:'行动项', creator_value:'创作者价值', review_object_id:'相关成果', instruction:'编写要求', intent:'要求类型',

  topic: "主题", text: "正文", value: "值", role: "角色", who: "人员", duty: "职责", decides: "决定事项",
  requirement: "要求", original_position: "原文位置", deliverable: "交付物", granularity: "颗粒度",
  spec: "规格", quantity: "数量", limits: "修改次数", external_dependencies: "外部依赖", note: "说明",
  round_key: "轮次", budget_kind: "口径", currency: "币种", min_minor: "金额下限", max_minor: "金额上限",
  applies_to: "适用范围", scope: "适用范围", raw: "原文金额", decided_by: "决定者", rationale: "理由", event: "事件",
  time_kind: "时间类型", date: "日期", start: "开始", end: "结束", source_note: "时间来源",
  context: "议题背景", options: "候选思路", asked_by: "提问方", answered_by: "答复方",
  question: "问题", status: "状态", follow_up: "跟进人", answer: "答复", answer_basis: "答复依据",
  related_object_ids: "关联对象", risk: "风险", trigger: "触发条件", impact: "影响", response: "应对",
  decision: "处理决定", to_verify: "待核实", meeting: "会议", meeting_at: "会议时间", focus: "议题",
  captures: "原话条目", block_ids: "作用段落", requirement: "要求", instruction_source: "指令来源",
  procurement_method: "采购方式", document_version: "文件版本", criteria: "评分标准", required_materials: "提交材料",
  submission_at: "截止时间", format: "格式", channel: "提交渠道", evidence_status: "信息状态",
  project_name: "历史项目", partner: "合作方", period: "时间", expression: "表达特点", feedback: "反馈",
  assessment: "评估判断", condition: "前置条件", capacity: "资源配置", gap: "待补缺口", rating: "评级",
  effective_at: "采用时间", participants: "参与人", action: "行动项", owner: "负责人", due_at: "截止时间", progress: "进展",
  name: "姓名 / 名称", kind: "种类", capability: "能力", works: "作品", availability: "档期", participation: "参与情况", venue: "场地",
  address: "地址", pages: "页数", caption: "图注", statement: "决定内容", supersedes_note: "历史关系",
};

/* ── 项目内：review ────────────────────────────────────────────────────── */
function viewReview(pid) {
  const c = el("div", "content wide");
  const proj = projOf(pid);
  const reviews = DATA.objects.filter((o) => o.project_id === pid && o.layer === "review");

  const head = el("div");
  head.style.margin = "30px 0 6px";
  const h = el("h1", "largetitle"); h.style.margin = "0 0 6px"; h.textContent = "整理与Review";
  const headingRow = el("div", "review-heading-row");
  const exportPrompt = btn("复制飞书导出 Prompt", () => copyText(reviewExportPrompt(DATA, pid), exportPrompt), "primary");
  exportPrompt.title = "复制后发送给 Agent，汇总全部成果与来源并新建飞书文档";
  exportPrompt.setAttribute("aria-live", "polite");
  headingRow.append(h, exportPrompt);
  head.append(headingRow);
  const sub = el("p", "subtitle");
  c.append(head);
  c.append(projectMonitorPanel(pid));

  const layout = el("div");
  layout.style.cssText = "display:grid;grid-template-columns:minmax(230px,280px) minmax(0,1fr);gap:26px;align-items:start;margin-top:20px;";
  layout.classList.add("object-layout");

  /* 左侧五类成果 */
  const nav = el("div", "card");
  const nh = el("header");
  const nh3 = el("h3"); nh3.textContent = "成果"; nh.append(nh3);
  nav.append(nh);
  const nb = el("div", "body");
  nb.style.padding = "14px";
  const ol = el("div", "objlist");
  for (const k of DATA.REVIEW_KINDS) {
    const isR05 = !k.persistable;
    let instances = [];
    if (isR05) {
      const qa = DATA.objects.find((o) => o.project_id === pid && o.type_key === "qa");
      if (qa && qa.current_revision_id) instances = [qa];
    } else {
      instances = reviews.filter((o) => o.type_key === k.type_key && o.current_revision_id);
    }
    const b = el("button", "objbtn" + (instances.length ? "" : " empty-obj"));
    b.type = "button";
    b.style.setProperty("--h", isR05 ? hueOf("teal") : hueOf("indigo"));
    if (S.route.objId === k.type_key || (instances[0] && S.route.objId === instances[0].id)) b.setAttribute("aria-current", "true");
    const cc = el("span", "ct");
    cc.textContent = k.code; cc.style.fontFamily = "var(--mono)"; cc.style.fontWeight = "700";
    cc.style.fontSize = "11px"; cc.style.color = isR05 ? hueOf("teal") : hueOf("indigo");
    b.append(cc);
    const nm = el("span", "nm"); nm.textContent = k.name; b.append(nm);
    const ct = el("span", "ct"); ct.textContent = instances.length ? instances.length + " 份" : "暂无";
    b.append(ct);
    b.onclick = () => go(`#/p/${pid}/review/${instances.length ? instances[0].id : k.type_key}`);
    ol.append(b);

    // 多实例：不同创作者、不同轮次各一份
    if (!isR05 && instances.length > 1) {
      const sub = el("div");
      sub.style.cssText = "margin:2px 0 8px 26px;display:flex;flex-direction:column;gap:2px;";
      for (const inst of instances) {
        const sb = el("button", "objbtn");
        sb.type = "button";
        sb.style.cssText = "font-size:12.5px;padding:4px 8px;";
        sb.style.setProperty("--h", hueOf("indigo"));
        if (S.route.objId === inst.id) sb.setAttribute("aria-current", "true");
        const sn = el("span", "nm");
        sn.textContent = instanceLabel(inst);
        sb.append(sn);
        sb.onclick = () => go(`#/p/${pid}/review/${inst.id}`);
        sub.append(sb);
      }
      ol.append(sub);
    }
  }
  nb.append(ol);
  nav.append(nb);
  layout.append(nav);

  /* 主体 */
  const main = el("div");
  const target = S.route.objId;
  let sel = null, kindMeta = null;
  if (target) kindMeta = DATA.REVIEW_KINDS.find((k) => k.type_key === target) || null;
  if (kindMeta && kindMeta.persistable) {
    sel = reviews.filter((o) => o.type_key === kindMeta.type_key && o.current_revision_id)[0] || null;
  } else if (kindMeta && !kindMeta.persistable) {
    sel = DATA.objects.find((o) => o.project_id === pid && o.type_key === "qa") || null;
  } else if (target) {
    sel = DATA.objects.find(o => o.id === target && o.project_id === pid && (o.layer === "review" || o.type_key === "qa")) || null;
    if (sel?.type_key === "qa") kindMeta = DATA.REVIEW_KINDS.find(k => !k.persistable);
    kindMeta = kindMeta || (sel ? DATA.REVIEW_KINDS.find((k) => k.type_key === sel.type_key) || null : null);
  }
  if (!sel && !kindMeta) {
    sel = reviews.filter((o) => o.current_revision_id)[0] || null;
    kindMeta = sel ? DATA.REVIEW_KINDS.find((k) => k.type_key === sel.type_key) : null;
  }

  if (kindMeta && !kindMeta.persistable) {
    sub.textContent = "客户 Q&A 与「信息收集」中的 D15 客户 Q&A 问题表共用同一份内容。";
    if (sel?.current_revision_id) {
      const openDraft = chipBtn("在信息收集中打开", () => go(`#/p/${pid}/draft/${sel.id}`));
      openDraft.style.marginLeft = "10px";
      sub.append(openDraft);
    }
    head.append(sub);
    main.append(qaReviewView(pid, sel, kindMeta));
  } else if (sel) {
    main.append(reviewDocument(sel, pid, kindMeta));
  } else if (kindMeta) {
    const card = el("div", "card");
    const bd = el("div", "body");
    bd.append(empty("✎", `尚未生成 ${kindMeta.name}`, []));
    card.append(bd);
    main.append(card);
  } else {
    main.append(empty("✎", "尚未生成成果", ["可以让 Agent 基于已有对象整理。"]));
  }

  // 导出记录
  const exps = DATA.exports.filter((e) => e.project_id === pid);
  if (exps.length && sel && sel.type_key === "debrief") {
    const ec = el("div", "card");
    const eh = el("header");
    const eh3 = el("h3"); eh3.textContent = "导出记录"; eh.append(eh3);
    const eg = el("span", "grow"); eh.append(eg);
    eh.append(tag("由 Agent 经 CLI 执行", "gray"));
    ec.append(eh);
    const eb = el("div", "body");
    for (const e of exps) {
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const k = el("div", "rel-k"); k.textContent = "飞书文档"; g.append(k);
      const v = el("div", "rel-v");
      const a = el("a"); a.href = e.external_url; a.target = "_blank"; a.rel = "noopener noreferrer";
      a.textContent = e.external_title; v.append(a); g.append(v);
      const m = el("div", "tiny muted"); m.style.marginTop = "4px";
      const rev = revOf(e.review_revision_id);
      m.textContent = `成果版本 v${rev ? rev.version : "?"} · 导出于 ${fullTime(e.exported_at)}`;
      g.append(m);
      row.append(g);
      eb.append(row);
    }
    const n = el("p", "tiny muted"); n.style.marginTop = "10px";
    n.textContent = "导出属于写操作，由 Agent 执行。页面只展示已记录的导出结果，不提供导出按钮。";
    eb.append(n);
    ec.append(eb);
    main.append(ec);
  }

  layout.append(main);
  c.append(layout);
  return c;
}

function instanceLabel(o) {
  const scope = o.scope_key || "";
  const m = scope.match(/creator:([^:]+):round:([^:]+)/);
  if (m) {
    const res = DATA.objects.find(r => r.project_id === o.project_id && r.type_key === "resources");
    const rev = headRev(res);
    let who = m[1];
    if (rev && rev.payload.items) {
      const it = rev.payload.items.find((x) => x.item_id === m[1]);
      if (it) who = it.data.name;
    }
    return `${who} · ${m[2]}`;
  }
  return scope || "整体";
}

/* review 文档阅读 */
function reviewDocument(o, pid, kindMeta) {
  const wrap = el("div");
  const rev = headRev(o);
  const versionWanted = S.versionOf[o.id];
  const shown = versionWanted ? (revsOf(o.id).find((r) => r.version === versionWanted) || rev) : rev;
  const isOld = shown.id !== rev.id;

  // 依据已变化：按段落检查，而非整份成果
  const staleBlocks = [];
  if (!isOld) {
    for (const b of shown.payload.blocks || []) {
      const st = blockBasisStatus(b.block_id, shown);
      if (st.stale.length) staleBlocks.push({ block_id: b.block_id, stale: st.stale });
    }
  }

  const card = el("div", "card");
  const head = el("header");
  head.style.padding = "18px 22px";
  head.append(codeChip(kindMeta ? kindMeta.code : "R", "indigo"));
  const h = el("h3"); h.style.fontSize = "19px"; h.textContent = (kindMeta ? kindMeta.name : shown.payload.title); head.append(h);
  if (o.scope_key && o.scope_key !== "project") head.append(tag(instanceLabel(o), "indigo"));
  const grow = el("span", "grow"); head.append(grow);
  head.append(tag("v" + shown.version, isOld ? "orange" : "green"));
  if (isOld) head.append(tag("历史版本", "orange"));
  head.append(copyRefButton({
    project_name: projOf(pid).name, project_id: pid,
    object_label: (kindMeta ? kindMeta.code + " " : "") + (kindMeta ? kindMeta.name : shown.payload.title) + `（${o.id}）`,
    version_label: "v" + shown.version + "（" + shown.id + "）",
  }));
  card.append(head);

  const bd = el("div", "body");
  bd.style.padding = "24px 26px";

  // 版本与确认记录
  const meta = el("div");
  meta.style.cssText = "display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:8px;";
  const mt = el("span", "tiny muted");
  mt.textContent = `v${shown.version} · 更新于 ${fullTime(shown.created_at)}`;
  meta.append(mt);
  const checks = DATA.review_checks.filter((x) => x.review_revision_id === shown.id);
  for (const ck of checks) {
    const m = DATA.CHECKS[ck.verdict] || { label: ck.verdict, hue: "gray" };
    const t = tag(m.label + " · " + ck.covered_blocks.join("/"), m.hue);
    t.title = ck.note;
    meta.append(t);
  }
  if (!checks.length) {
    const t = tag("尚无确认记录", "gray");
    t.title = "当前版本尚未接入确认记录，页面不推定审核状态。";
    meta.append(t);
  }
  bd.append(meta);

  if (isOld) {
    const other = rev;
    bd.append(banner("orange", "◷", [
      (() => { const p = el("p"); p.style.margin = "0"; p.innerHTML = `正在阅读 <b>v${shown.version}</b>（历史版本）。当前版本是 v${other.version}。`; return p; })(),
      (() => { const d = el("div"); d.style.marginTop = "8px"; d.append(chipBtn("回到当前版本", () => { delete S.versionOf[o.id]; render(); })); return d; })(),
    ]));
  }

  if (staleBlocks.length) {
    bd.append(banner("orange", "↻", [
      (() => { const p = el("p"); p.style.margin = "0"; p.innerHTML = `<b>依据已变化 · 成果尚未同步</b>：${staleBlocks.length} 个段落的 draft 依据或其上游内容已有变化，当前成果尚未同步。`; return p; })(),
      (() => {
        const d = el("div", "review-prompt-actions");
        const updatePrompt = btn("复制更新 Prompt", () => copyText(reviewUpdatePrompt(DATA, pid, o.id), updatePrompt));
        updatePrompt.setAttribute("aria-live", "polite");
        d.append(updatePrompt);
        d.append(chipBtn("查看受影响段落", () => {
          const first = document.querySelector(`[data-block="${staleBlocks[0].block_id}"]`);
          if (first) first.scrollIntoView({ behavior: "smooth", block: "center" });
        }));
        return d;
      })(),
    ]));
  }

  // 正文
  const doc = el("div", "doc");
  const order = (shown.payload.block_order && shown.payload.block_order.length ? shown.payload.block_order : shown.payload.blocks.map((b) => b.block_id));
  for (const bid of order) {
    const b = shown.payload.blocks.find((x) => x.block_id === bid);
    if (!b) continue;
    const st = blockBasisStatus(bid, shown);
    const isStale = !isOld && st.stale.length > 0;

    const blk = el("div", "block" + (isStale ? " stale" : ""));
    blk.dataset.block = bid;
    const bh = el("div", "bhead");
    const bt = el("h4", "btitle"); bt.textContent = (intentLabel(kindMeta, bid) || b.markdown.match(/^#{1,6}\s+(.+)$/m)?.[1] || "成果段落");
    bh.append(bt);
    const bg = el("span", "grow"); bh.append(bg);
    if (isStale) bh.append(tag("依据已变化", "orange", true));
    if (!st.known) bh.append(tag("依据无法完整核对", "orange", true));

    blk.append(bh);

    const txt = el("div", "btext");
    const leadingTitle = b.markdown.match(/^\s*#{1,6}\s+([^\n]+)\n?/);
    const displayBody = leadingTitle && leadingTitle[1].trim() === bt.textContent ? b.markdown.slice(leadingTitle[0].length) : b.markdown;
    txt.append(renderMarkdown(displayBody));
    blk.append(txt);

    if (isStale) {
      const note = el("div", "bnote");
      const ic = el("span"); ic.textContent = "▸"; note.append(ic);
      const nt = el("div");
      nt.style.flex = "1";
      const parts = st.stale.map((s) => {
        const so = oOf(s.object_id);
        const nr = revOf(so && so.current_revision_id);
        const name = `${typeCode(so?.type_key) || ""} ${so ? typeName(so.type_key) : s.object_id}`;
        return nr?.id === s.revision_id ? `${name}：其引用的上游依据已变化` : `${name}：段落基于 v${revOf(s.revision_id)?.version ?? "?"}，当前已是 v${nr?.version ?? "?"}`;
      });
      nt.textContent = parts.join("；");
      note.append(nt);
      blk.append(note);
    }

    blk.append((() => {
      const d = el("div");
      d.className = "review-block-actions";
      if (isStale) {
        const diff = chipBtn("查看差异", () => openInspector({ kind: "basis", object_id: st.stale[0].object_id, revision_id: st.stale[0].revision_id, item_id: st.stale[0].item_id, block_id: bid, review_id: o.id }));
        diff.classList.add("diff-trigger");
        d.append(diff);
      }
      d.append(chipBtn("完整追溯路径", () => openInspector({ kind: "trace", review_id: o.id, block_id: bid })));
      d.append(copyRefButton({
        project_name: projOf(pid).name, project_id: pid,
        object_label: (kindMeta ? kindMeta.code + " " : "") + (kindMeta ? kindMeta.name : shown.payload.title) + `（${o.id}）`,
        block_label: bid + "（" + (intentLabel(kindMeta, bid) || b.markdown.match(/^#{1,6}\s+(.+)$/m)?.[1] || "成果段落") + "）",
        version_label: "v" + shown.version + "（" + shown.id + "）",
        excerpt: b.markdown.replace(/[*#\-]/g, "").slice(0, 80),
      }));
      return d;
    })());
    doc.append(blk);
  }
  bd.append(doc);

  const note = el("p", "tiny muted");
  note.style.marginTop = "20px";
  note.textContent = "修改请在 Codex 中提出：反馈会先落到相关 draft 对象，再由 Agent 更新成果。页面不提供直接编辑。";
  bd.append(note);

  card.append(bd);
  wrap.append(card);

  // 版本历史
  const allRevs = revsOf(o.id);
  if (allRevs.length > 1) {
    const hc = el("div", "card");
    const hh = el("header");
    const hh3 = el("h3"); hh3.textContent = "版本"; hh.append(hh3);
    const hg = el("span", "grow"); hh.append(hg);
    hh.append(tag(allRevs.length + " 版", "gray"));
    hc.append(hh);
    const hb = el("div", "body tight");
    const tl = el("div", "tl");
    for (const r of allRevs.slice().reverse()) {
      const row = el("div", "tlrow");
      row.style.setProperty("--h", r.id === rev.id ? hueOf("green") : hueOf("gray"));
      const top = el("div", "t");
      top.append(tag("v" + r.version, r.id === rev.id ? "green" : "gray"));
      const w = el("span", "when"); w.textContent = fullTime(r.created_at); top.append(w);
      row.append(top);
      const chg = DATA.changes.find((x) => x.id === r.change_id);
      const rs = el("div", "reason"); rs.textContent = chg ? chg.reason : "尚未记录变更说明"; row.append(rs);
      row.append(chipBtn("查看", () => { S.versionOf[o.id] = r.version; render(); }));
      tl.append(row);
    }
    hb.append(tl);
    hc.append(hb);
    wrap.append(hc);
  }
  return wrap;
}

// 段落的中文小标题（依据块 ID 命名，便于阅读）
const INTENT_LABELS = {
  why: "客户为何做", goal: "要解决什么", audience: "面向谁", who_decides: "谁决定什么",
  scope: "本轮交付与边界", budget: "预算",
  plan_deliver: "本轮交付", plan_nodes: "关键节点", plan_owners: "相关职责",
  cr_target: "目标审查", cr_direction: "方向取舍", cr_investment: "投入重点", cr_pending: "待讨论",
  cb_background: "任务背景", cb_task: "要解决的问题", cb_deliver: "交付要求", cb_schedule: "日期",
  cb_collab: "协作与职责", cb_limits: "使用边界",
};
const intentLabel = (kindMeta, bid) => INTENT_LABELS[bid] || null;

/* R05：展示 D15 的同一份问题表 */
function qaReviewView(pid, qaObj, kindMeta) {
  const wrap = el("div");
  const rev = qaObj ? headRev(qaObj) : null;
  const card = el("div", "card");
  const head = el("header");
  head.style.padding = "18px 22px";
  head.append(codeChip("R05", "teal"));
  const h = el("h3"); h.style.fontSize = "19px"; h.textContent = "客户 Q&A"; head.append(h);
  const grow = el("span", "grow"); head.append(grow);
  if (rev) head.append(tag("同 D15 · v" + rev.version, "teal"));
  card.append(head);

  const bd = el("div", "body");
  bd.style.padding = "22px 24px";
  if (!rev) {
    bd.append(empty("?", "尚未建立问题表", ["D15 客户 Q&A 尚未录入。可以让 Agent 从已有对象中整理待确认问题。"]));
    card.append(bd);
    wrap.append(card);
    return wrap;
  }
  const meta = el("div", "tiny muted");
  meta.style.marginBottom = "18px";
  meta.textContent = `v${rev.version} · 更新于 ${fullTime(rev.created_at)}`;
  bd.append(meta);

  const items = rev.payload.items || [];
  const answered = items.filter((i) => qaState(i.data.status).answered).length;
  const stats = el("div", "grid g3");
  stats.style.marginBottom = "18px";
  const st = (v, l) => { const d = el("div", "stat"); const b = el("b"); b.textContent = v; d.append(b); const s = el("span"); s.textContent = l; d.append(s); return d; };
  stats.append(st(items.length, "问题总数"), st(answered, "已答复"), st(items.length - answered, DATA.meta.demo === false ? "其他状态" : "待答复或不适用"));
  bd.append(stats);

  const tl = el("div", "tl");
  for (const it of items) {
    const row = el("div", "tlrow");
    const st2 = qaState(it.data.status);
    row.style.setProperty("--h", hueOf(st2.hue));
    const top = el("div", "t");
    top.append(tag(st2.label, st2.hue, true));
    if (it.data.follow_up_person || it.data.follow_up) { const f = el("span", "when"); f.textContent = "跟进：" + (it.data.follow_up_person || it.data.follow_up); top.append(f); }
    row.append(top);
    const q = el("div"); q.style.cssText = "font-weight:600;font-size:14.5px;"; q.textContent = it.data.question; row.append(q);
    if (it.data.asked_by || it.data.answered_by) {
      const parties = el('div', 'small muted');
      parties.textContent = [it.data.asked_by && '提问方：' + it.data.asked_by, it.data.answered_by && '答复方：' + it.data.answered_by].filter(Boolean).join(' · ');
      row.append(parties);
    }
    if (it.data.answer) {
      const a = el("div"); a.style.cssText = "font-size:14px;margin-top:6px;color:var(--label-2);"; a.textContent = "答复：" + it.data.answer; row.append(a);
    } else if (it.data.note) {
      const a = el("div", "small muted"); a.style.marginTop = "6px"; a.textContent = it.data.note; row.append(a);
    } else {
      const a = el("div", "small muted"); a.style.marginTop = "6px"; a.textContent = "尚无答复。"; row.append(a);
    }
    const rel = (it.data.related_object_ids || []).map((id) => oOf(id)).filter(Boolean);
    if (rel.length) {
      const rb = el("div", "cites");
      for (const ro of rel) {
        const c2 = el("button", "cite");
        c2.type = "button";
        c2.style.setProperty("--h", hueOf((themeOf(ro.type_key) || {}).hue || "gray"));
        c2.textContent = (typeCode(ro.type_key) || "") + " " + typeName(ro.type_key);
        c2.onclick = () => go(`#/p/${pid}/draft/${ro.id}`);
        rb.append(c2);
      }
      row.append(rb);
    }
    row.append(sourceLinksOf(it));
    tl.append(row);
  }
  bd.append(tl);
  card.append(bd);
  wrap.append(card);
  return wrap;
}

/* ── 项目内：材料与来源 ────────────────────────────────────────────────── */
function viewSources(pid) {
  const c = el("div", "content wide");
  const srcs = DATA.sources.filter((s) => s.project_id === pid);

  const head = el("div");
  head.style.margin = "30px 0 6px";
  const h = el("h1", "largetitle"); h.style.margin = "0 0 6px"; h.textContent = "原始材料";
  head.append(h);
  const sub = el("p", "subtitle");
  sub.textContent = "飞书、本地文件与用户补充统一在这里。对象里的来源引用与这里是同一份来源身份，不是两个材料库。";
  head.append(sub);
  c.append(head);

  const groups = ["feishu", "local", "oral", "web"];
  for (const prov of groups) {
    const list = srcs.filter((s) => s.provider === prov);
    if (!list.length) continue;
    const pm = DATA.PROVIDERS[prov];
    const gh = el("div");
    gh.style.cssText = "display:flex;align-items:center;gap:9px;margin:28px 0 10px;";
    const gd = el("span"); gd.style.cssText = `width:9px;height:9px;border-radius:50%;background:${hueOf(pm.hue)};`;
    gh.append(gd);
    const gt = el("h2"); gt.style.cssText = "font-size:13px;font-weight:660;letter-spacing:.05em;text-transform:uppercase;color:var(--label-3);";
    gt.textContent = pm.label; gh.append(gt);
    const gn = el("span", "tiny muted"); gn.textContent = list.length + " 份"; gh.append(gn);
    c.append(gh);

    const g = el("div", "listgroup");
    for (const s of list) {
      const vers = DATA.source_versions.filter((v) => v.source_id === s.id);
      const usedBy = vers.flatMap((v) => itemsUsingSourceVersion(v.id));
      const row = el("div", "lrow clickable");
      row.onclick = () => openInspector({ kind: "source", id: s.id, sv: s.latest_snapshot_id });
      row.tabIndex = 0; row.setAttribute("role", "button");
      row.setAttribute("aria-label", "查看材料：" + (s.cached_title || "标题尚未取得"));
      row.onkeydown = e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); row.click(); } };
      const ic = el("span");
      ic.style.cssText = `width:34px;height:34px;border-radius:9px;flex:none;display:grid;place-items:center;font-size:15px;background:color-mix(in srgb, ${hueOf(pm.hue)} 14%, transparent);color:${hueOf(pm.hue)};`;
      ic.textContent = { doc: "📄", folder: "📁", mic: "🎙", globe: "🔗" }[pm.icon] || "📄";
      row.append(ic);
      const g2 = el("div", "grow");
      const h4 = el("h4"); h4.textContent = s.cached_title || "标题尚未取得";
      if (!s.cached_title) h4.style.color = "var(--label-3)";
      g2.append(h4);
      const s2 = el("div", "sub");
      s2.textContent = [
        s.resource_type,
        vers.length + " 个快照",
        usedBy.length ? usedBy.length + " 处引用" : "尚无对象引用",
      ].join(" · ");
      g2.append(s2);
      const badges = el("div");
      badges.style.cssText = "margin-top:7px;display:flex;gap:6px;flex-wrap:wrap;";
      if (s.check_error) badges.append(tag(s.check_error.code === "FILE_NOT_FOUND" ? "原件不可用" : "读取失败", "orange", true));
      if (s.remote_observation && s.remote_observation.conclusion === "changed") badges.append(tag("远端有更新", "orange", true));
      if (!s.check_error && s.remote_observation?.conclusion === "unchanged") badges.append(tag("检查时远端未变化", "green", true));
      if (s.remote_observation?.conclusion === "unknown") badges.append(tag("缺少比较基线", "gray"));
      if (!s.last_checked_at && s.provider === "feishu") badges.append(tag("尚未检查远端", "gray"));
      g2.append(badges);
      row.append(g2);
      const rt = el("div", "tiny muted");
      rt.style.cssText = "flex:none;text-align:right;font-variant-numeric:tabular-nums;";
      rt.textContent = when(s.created_at);
      row.append(rt);
      g.append(row);

      // 未引用材料的诚实说明
      if (!usedBy.length) {
        const n = el("div");
        n.style.cssText = "padding:0 20px 14px 68px;margin-top:-6px;";
        const p = el("p", "tiny muted");
        p.style.margin = "0";
        p.textContent = "材料已保存但尚未被任何对象引用。这不代表未读、无用或出错。";
        n.append(p);
        g.append(n);
      }
    }
    c.append(g);
  }
  return c;
}

/* ── 项目内：历史 ──────────────────────────────────────────────────────── */
function viewHistory(pid) {
  const c = el("div", "content wide");
  const changes = DATA.changes.filter((x) => x.project_id === pid).slice().sort((a, b) => b.seq - a.seq);
  const decisions = DATA.decisions.filter((d) => d.project_id === pid);

  const head = el("div");
  head.style.margin = "30px 0 6px";
  const h = el("h1", "largetitle"); h.style.margin = "0 0 6px"; h.textContent = "变更与决定记录";
  head.append(h);
  const sub = el("p", "subtitle");
  sub.textContent = "这里是已保存的变更记录与正式决定，不是聊天全文，也不是 Agent 的执行过程日志。";
  head.append(sub);
  c.append(head);

  const tab = el("div", "tabbar");
  const mode = S.route.sub || "changes";
  for (const [k, label, n] of [["changes", "变更记录", changes.length], ["decisions", "正式决策", decisions.length]]) {
    const b = el("button", "chipbtn");
    b.type = "button";
    b.textContent = label + "  " + n;
    if (mode === k) { b.style.background = "var(--label)"; b.style.color = "#fff"; }
    b.onclick = () => go(`#/p/${pid}/history/${k}`);
    tab.append(b);
  }
  c.append(tab);
  c.append((() => { const d = el("div"); d.style.height = "18px"; return d; })());

  if (mode === "decisions") {
    const g = el("div");
    g.style.marginTop = "6px";
    for (const d of decisions.slice().reverse()) {
      const card = el("div", "card");
      const head2 = el("header");
      const st = el("span");
      st.style.cssText = `width:9px;height:9px;border-radius:50%;background:${hueOf("indigo")};`;
      head2.append(st);
      const h3 = el("h3"); h3.textContent = d.statement; h3.style.fontSize = "15.5px"; head2.append(h3);
      const gr = el("span", "grow"); head2.append(gr);
      head2.append(tag("决定者：" + d.decided_by, "indigo"));
      card.append(head2);
      const bd = el("div", "body");
      bd.append(kv([
        ["记录时间", fullTime(d.created_at)],
        ["理由", d.rationale],
        ["指令来源", (() => { const sv = svOf(d.instruction_source_version_id); if (!sv) return "尚未记录"; const w = el("span"); w.append(sourceLink(sv.id)); return w; })()],
        ["影响范围", (() => {
          const w = el("div", "cites");
          for (const r of d.affected_refs) {
            const o = oOf(r.object_id);
            if (!o) continue;
            const c2 = el("button", "cite");
            c2.type = "button";
            c2.style.setProperty("--h", hueOf((themeOf(o.type_key) || {}).hue || (o.layer === "review" ? "indigo" : "gray")));
            c2.textContent = (typeCode(o.type_key) || "") + " " + typeName(o.type_key) + (r.block_id ? " · " + r.block_id : r.item_id ? " · " + r.item_id : "");
            c2.onclick = () => go(`#/p/${pid}/${o.layer}/${o.id}`);
            w.append(c2);
          }
          return w;
        })()],
      ]));
      if (d.supersedes_id) {
        const old = DATA.decisions.find((x) => x.id === d.supersedes_id);
        const n = el("div");
        n.style.marginTop = "14px";
        n.append(banner("gray", "←", [
          (() => { const p = el("p"); p.style.margin = "0"; p.innerHTML = `本决定替代了旧决定：<b>${esc(old ? old.statement : d.supersedes_id)}</b>（记录于 ${fullTime(old ? old.created_at : null)}）。旧决定仍可查看。`; return p; })(),
        ]));
        bd.append(n);
      }
      card.append(bd);
      g.append(card);
    }
    if (!decisions.length) g.append(empty("◆", "尚无正式决策", ["正式决定会在 Agent 通过 draft 修改记录时一并保存。"]));
    c.append(g);
    return c;
  }

  const g = el("div", "listgroup");
  for (const ch of changes) {
    const row = el("div", "lrow");
    const ic = el("span");
    const isNoop = ch.effect === "noop";
    ic.style.cssText = `width:30px;height:30px;border-radius:8px;flex:none;display:grid;place-items:center;font-size:13px;background:color-mix(in srgb, ${hueOf(isNoop ? "gray" : "blue")} 12%, transparent);color:${hueOf(isNoop ? "gray" : "blue")};`;
    ic.textContent = isNoop ? "∅" : "＋";
    row.append(ic);
    const g2 = el("div", "grow");
    const h4 = el("h4"); h4.textContent = ch.reason; g2.append(h4);
    const s2 = el("div", "sub");
    s2.textContent = `${ch.command} · ${fullTime(ch.created_at)}`;
    g2.append(s2);
    if (isNoop) {
      const n = el("div", "tiny muted"); n.style.marginTop = "6px";
      n.textContent = "本次提交没有产生业务变化（noop 回执），因此没有新版本。";
      g2.append(n);
    }
    const refs = el("div");
    refs.style.cssText = "margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;";
    for (const r of (ch.changed_refs || [])) {
      const o = oOf(r.object_id);
      if (!o) continue;
      const c3 = el("button", "cite");
      c3.type = "button";
      c3.style.setProperty("--h", hueOf((themeOf(o.type_key) || {}).hue || (o.layer === "review" ? "indigo" : "gray")));
      c3.textContent = (typeCode(o.type_key) || "") + " " + typeName(o.type_key);
      c3.onclick = () => go(`#/p/${pid}/${o.layer}/${o.id}`);
      refs.append(c3);
    }
    if (ch.causal_change_ids && ch.causal_change_ids.length) {
      const t = tag("因果：" + ch.causal_change_ids.join(" "), "purple");
      t.title = "这条变更由这些更早的 draft 变更引起";
      refs.append(t);
    }
    g2.append(refs);
    row.append(g2);
    g.append(row);
  }
  if (!changes.length) g.append(empty("◷", "尚无变更记录", []));
  c.append(g);
  return c;
}

/* ── 对象属性目录 ──────────────────────────────────────────────────────── */
function viewCatalog() {
  const c = el("div", "content wide");
  const h = el("h1", "largetitle"); h.textContent = "对象说明"; c.append(h);
  const sub = el("p", "subtitle");
  sub.textContent = `${DATA.catalog.length} 类业务对象的名称与作用。页面中的「对象说明」从这里派生，与 Agent 使用的定义是同一套。`;
  c.append(sub);

  c.append((() => { const d = el("div"); d.style.height = "8px"; return d; })());

  const card = el("div", "card");
  const head = el("header");
  const h3 = el("h3"); h3.textContent = "信息收集对象"; head.append(h3);
  const g = el("span", "grow"); head.append(g);
  head.append(tag(`${DATA.catalog.length} 类`, "blue"));
  card.append(head);
  const bd = el("div", "body");
  bd.style.padding = "0";
  const tb = el("table");
  const thead = el("thead");
  const tr = el("tr");
  for (const t of ["编号", "对象", "这是什么", "归属边界", "可能来源", "用途与承接"]) {
    const th = el("th"); th.textContent = t; tr.append(th);
  }
  thead.append(tr); tb.append(thead);
  const tbody = el("tbody");
  for (const k of DATA.catalog) {
    const row = el("tr");
    const td0 = el("td");
    td0.append(codeChip(k.code, (themeOf(k.type_key) || {}).hue || "gray"));
    row.append(td0);
    const td1 = el("td"); td1.style.fontWeight = "620"; td1.textContent = k.name; row.append(td1);
    const td2 = el("td", "small"); td2.textContent = k.meaning; td2.style.maxWidth = "26ch"; row.append(td2);
    const td3 = el("td", "small"); td3.style.color = "var(--orange)"; td3.textContent = k.boundary; td3.style.maxWidth = "24ch"; row.append(td3);
    const td4 = el("td", "small muted"); td4.textContent = k.sources; td4.style.maxWidth = "22ch"; row.append(td4);
    const td5 = el("td", "small muted"); td5.textContent = k.usage; td5.style.maxWidth = "20ch"; row.append(td5);
    tbody.append(row);
  }
  tb.append(tbody);
  bd.append(tb);
  card.append(bd);
  c.append(card);

  const rc = el("div", "card");
  const rh = el("header");
  const rh3 = el("h3"); rh3.textContent = "review 成果"; rh.append(rh3);
  const rg = el("span", "grow"); rh.append(rg);
  rh.append(tag("5 类", "indigo"));
  rc.append(rh);
  const rb = el("div", "body");
  for (const k of DATA.REVIEW_KINDS) {
    const row = el("div", "relrow");
    const g2 = el("div", "grow");
    const top = el("div");
    top.style.cssText = "display:flex;gap:8px;align-items:center;flex-wrap:wrap;";
    top.append(codeChip(k.code, k.persistable ? "indigo" : "teal"));
    const nm = el("b"); nm.textContent = k.name; top.append(nm);
    if (!k.persistable) top.append(tag("读取 D15，不单独持久化", "teal"));
    g2.append(top);
    const m = el("div", "small"); m.style.marginTop = "6px"; m.textContent = k.meaning; g2.append(m);
    const b2 = el("div", "tiny muted"); b2.style.marginTop = "4px"; b2.textContent = "主要依据：" + k.basis; g2.append(b2);
    row.append(g2);
    rb.append(row);
  }
  rc.append(rb);
  c.append(rc);

  const ic = el("div", "card");
  const ih = el("header");
  const ih3 = el("h3"); ih3.textContent = "内部类型"; ih.append(ih3);
  ic.append(ih);
  const ib = el("div", "body");
  for (const t of DATA.internal_types) {
    const row = el("div", "relrow");
    const g2 = el("div", "grow");
    const nm = el("b"); nm.textContent = t.name; g2.append(nm);
    const m = el("div", "small"); m.style.marginTop = "5px"; m.textContent = t.meaning; g2.append(m);
    const b2 = el("div", "tiny muted"); b2.style.marginTop = "4px"; b2.textContent = "边界：" + t.boundary; g2.append(b2);
    row.append(g2);
    ib.append(row);
  }
  ic.append(ib);
  c.append(ic);

  // 信息性质图例：颜色本身可读
  const lc = el("div", "card");
  const lh = el("header");
  const lh3 = el("h3"); lh3.textContent = "信息性质"; lh.append(lh3);
  const lg = el("span", "grow"); lh.append(lg);
  lh.append(tag("不可把推断显示成客户原话", "orange"));
  lc.append(lh);
  const lb = el("div", "body");
  const grid = el("div", "grid g3");
  for (const [k, m] of Object.entries(DATA.EPISTEMIC)) {
    const d = el("div", "relrow");
    const g2 = el("div", "grow");
    const top = el("div"); top.style.marginBottom = "5px"; top.append(epistemicTag(k));
    g2.append(top);
    const p = el("div", "small muted"); p.textContent = m.hint; g2.append(p);
    d.append(g2);
    grid.append(d);
  }
  lb.append(grid);
  lc.append(lb);
  c.append(lc);
  return c;
}

/* Saved Markdown only: DOM text rendering, no HTML or executable URLs. */
function renderMarkdown(md) {
  const box = el('div');
  const lines=String(md||'').split('\n');
  const inline=(text)=>{
    const span=el('span');
    const pattern=/(\*\*[^*]+\*\*|`[^`]+`|!?\[[^\]]*\]\([^\s)]+\))/g;
    let at=0;
    for(const match of String(text).matchAll(pattern)){
      span.append(document.createTextNode(text.slice(at,match.index)));
      const token=match[0];
      if(token.startsWith('**')){const strong=el('strong');strong.textContent=token.slice(2,-2);span.append(strong);}
      else if(token.startsWith('`')){const code=el('code');code.textContent=token.slice(1,-1);span.append(code);}
      else {
        const link=token.match(/^!?\[([^\]]*)\]\(([^)]+)\)$/);
        let safe=false;
        try {const url=new URL(link[2],location.href); safe=['http:','https:'].includes(url.protocol) && (!link[2].startsWith('/') || url.origin===location.origin);}catch{}
        if(safe){const a=el('a');a.textContent=link[1]||link[2];a.href=link[2];a.target='_blank';a.rel='noopener noreferrer';span.append(a);}
        else span.append(document.createTextNode(token));
      }
      at=match.index+token.length;
    }
    span.append(document.createTextNode(text.slice(at)));return span;
  };
  let list=null;
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(/^\s*(```+|~~~+)/.test(line)){
      list=null;const fence=line.trim().match(/^(`+|~+)/)[0];const content=[];
      while(++i<lines.length && !lines[i].trim().startsWith(fence))content.push(lines[i]);
      const pre=el('pre');pre.textContent=content.join('\n');box.append(pre);continue;
    }
    if(line.includes('|') && /^\s*\|?\s*:?-{3,}:?\s*\|/.test(lines[i+1]||'')){
      list=null;const table=el('table');table.style.cssText='width:100%;border-collapse:collapse';
      const cells=text=>text.trim().replace(/^\||\|$/g,'').split('|').map(v=>v.trim());
      const add=(text,header)=>{const tr=el('tr');for(const cell of cells(text)){const td=el(header?'th':'td');td.style.cssText='padding:8px;text-align:left;border-bottom:1px solid var(--separator)';td.append(inline(cell));tr.append(td);}table.append(tr);};
      add(line,true);i++;
      while(i+1<lines.length && lines[i+1].trim() && lines[i+1].includes('|'))add(lines[++i],false);
      box.append(table);continue;
    }
    const li=line.match(/^\s*(?:([-*])|\d+[.)])\s+(.*)$/);
    if(li){const kind=li[1]?'ul':'ol';if(!list || list.tagName.toLowerCase()!==kind){list=el(kind);box.append(list);}const item=el('li');item.append(inline(li[2]));list.append(item);continue;}
    list=null;
    const heading=line.match(/^(#{1,6})\s+(.*)$/);
    if(heading){const h=el('h'+Math.min(6,heading[1].length+1));h.append(inline(heading[2]));box.append(h);continue;}
    if(!line.trim())continue;
    const p=el(line.startsWith('> ')?'blockquote':'p');p.append(inline(line.replace(/^> /,'')));box.append(p);
  }
  return box;
}

/* ═══════════════════════════ 顶栏与侧栏 ═══════════════════════════════ */
function updateMainNavigationToggle() {
  const button = $("mainNavToggle");
  const label = S.mainNavCollapsed ? "展开主导航" : "收起主导航";
  button.setAttribute("aria-label", label);
  button.setAttribute("aria-expanded", String(!S.mainNavCollapsed));
  button.title = label;
  setPanelToggleIcon(button, S.mainNavCollapsed);
  button.onclick = () => animatePanelToggle(document.body, $("navigation"), () => {
    S.mainNavCollapsed = !S.mainNavCollapsed;
    document.body.classList.toggle("main-nav-collapsed", S.mainNavCollapsed);
    updateMainNavigationToggle();
  });
}
function renderChrome() {
  updateMainNavigationToggle();
  const tb = $("toolbar"); tb.replaceChildren();
  const r = S.route;
  document.documentElement.classList.toggle("reading-draft", r.view === "draft");
  tb.classList.toggle("project-toolbar", r.view === "projects");
  tb.classList.toggle("catalog-toolbar", r.view === "types");

  const crumbs = el("div", "crumbs");
  const proj = r.pid ? projOf(r.pid) : null;
  if (proj) {
    const pb = el("span", "projectbadge");
    const dot = el("span", "dot");
    dot.style.background = hueOf(themeHueForProject(proj.id));
    pb.append(dot, document.createTextNode(proj.name));
    pb.title = "当前浏览项目：" + proj.name + "（" + proj.id + "）";
    crumbs.append(pb);
    const sep2 = el("span", "sep"); sep2.textContent = "›"; crumbs.append(sep2);
    const sec = r.view === "review" ? "整理与Review" : r.view === "sources" ? "原始材料" : r.view === "history" ? "变更与决定记录" : "信息收集";
    const b = el("b"); b.textContent = sec; crumbs.append(b);
  }
  const menu = btn("☰", () => {
    document.body.classList.toggle("navigation-open");
    menu.setAttribute("aria-expanded", String(document.body.classList.contains("navigation-open")));
  }, "sm mobile-menu");
  menu.setAttribute("aria-label", "展开或收起导航");
  menu.setAttribute("aria-controls", "navigation");
  menu.setAttribute("aria-expanded", String(document.body.classList.contains("navigation-open")));
  tb.append(menu);
  if (r.view === "projects") {
    const heading = el("h1", "largetitle"); heading.textContent = "项目";
    tb.append(heading);
  } else {
    tb.append(crumbs);
  }
  tb.append((() => { const s = el("span", "grow"); return s; })());

  // 侧栏
  const sm = $("sideMain"); sm.replaceChildren();
  const addNav = (parent, label, hash, opts) => {
    const b = el("button");
    b.type = "button";
    if (opts && opts.current) b.setAttribute("aria-current", "page");
    const ic = el("span", "ic"); ic.textContent = opts.icon || ""; b.append(ic);
    const text = el("span", "nav-label"); text.textContent = label; b.append(text);
    b.setAttribute("aria-label", label); b.title = label;
    if (opts && opts.n != null) { const n = el("span", "n"); n.textContent = opts.n; b.append(n); }
    b.onclick = () => go(hash);
    parent.append(b);
    return b;
  };
  addNav(sm, "项目", "#/", { icon: "▦", current: S.route.view === "projects" });
  addNav(sm, "对象说明", "#/types", { icon: "◇", current: S.route.view === "types", n: String(DATA.catalog.length) });

  const sp = $("sideProject"); sp.replaceChildren();
  const secondary = $("sideProjectSecondary"); secondary.replaceChildren();
  if (proj) {
    addNav(sp, "信息收集", `#/p/${proj.id}/draft`, { icon: "✎", current: S.route.view === "draft" });
    addNav(sp, "整理与Review", `#/p/${proj.id}/review`, { icon: "▤", current: S.route.view === "review" });
    addNav(secondary, "原始材料", `#/p/${proj.id}/sources`, { icon: "❖", current: S.route.view === "sources" });
    addNav(secondary, "变更与决定记录", `#/p/${proj.id}/history`, { icon: "◷", current: S.route.view === "history" });
  } else {
    const info = el("div");
    info.style.cssText = "padding:6px 10px;font-size:12px;color:var(--label-3);line-height:1.6;";
    info.textContent = "进入一个项目后，这里显示它的信息收集、整理与Review、材料与历史。";
    sp.append(info);
  }

  const refreshedAt = el("time");
  refreshedAt.dateTime = pageLoadedAt.toISOString();
  refreshedAt.textContent = fullTime(pageLoadedAt) + ":" + String(pageLoadedAt.getSeconds()).padStart(2, "0");
  const refreshLabel = el("span");
  refreshLabel.append(DATA.meta.demo ? "模拟预览 · 刷新于 " : "本地数据 · 刷新于 ", refreshedAt);
  const refreshButton = chipBtn("", () => { S.inspector = null; loadRoute(true); });
  refreshButton.classList.add("page-refresh");
  refreshButton.setAttribute("aria-label", "刷新页面");
  refreshButton.title = "刷新页面";
  const refreshIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  refreshIcon.setAttribute("viewBox", "0 0 24 24");
  refreshIcon.setAttribute("width", "16"); refreshIcon.setAttribute("height", "16");
  refreshIcon.setAttribute("aria-hidden", "true");
  refreshIcon.innerHTML = '<g fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7v5h-5"/><path d="M20 12a8 8 0 1 0-2.3 5.7"/></g>';
  refreshButton.append(refreshIcon);
  $("railFoot").replaceChildren(refreshLabel, refreshButton);
}

/* ═══════════════════════════ 路由 ═════════════════════════════════════ */
function parseRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const parts = raw.split("/").filter(Boolean);
  const r = { view: "projects", pid: null, objId: null, sub: null };
  if (!parts.length) return r;
  if (parts[0] === "types") { r.view = "types"; return r; }
  if (parts[0] === "p" && parts[1]) {
    r.pid = parts[1];
    r.view = parts[2] || "draft";
    r.objId = parts[3] || null;
    r.sub = parts[3] || null;
    if (!["draft", "review", "sources", "history"].includes(r.view)) { r.view = "draft"; r.objId = null; }
  }
  return r;
}
function go(hash) {
  if (location.hash === hash) {
    render();
    if (S.route.view === "draft" && S.route.objId) scrollToDraft(S.route.objId);
  } else location.hash = hash;
}

const toolbarSizeObserver = new ResizeObserver(() => {
  document.documentElement.style.setProperty("--toolbar-height", `${$("toolbar").getBoundingClientRect().height}px`);
});
toolbarSizeObserver.observe($("toolbar"));

const projectDockObserver = new ResizeObserver(entries => {
  for (const { target } of entries) {
    document.documentElement.style.setProperty("--project-dock-height", `${target.getBoundingClientRect().height}px`);
  }
});

function renderStage(updateChrome = true) {
  const nextRoute = parseRoute();
  const anchor = S.route?.view === "draft" && nextRoute.view === "draft" && S.route.pid === nextRoute.pid
    ? draftReadingAnchor() : null;
  projectDockObserver.disconnect();
  S.route = parseRoute();
  if (updateChrome) renderChrome();
  const stage = $("stage");
  stage.replaceChildren();

  const proj = S.route.pid ? projOf(S.route.pid) : null;
  if (S.route.pid && !proj) {
    const c = el("div", "content");
    c.append(empty("?", "项目不存在", ["该 project_id 在本机数据目录中没有对应项目。"]));
    stage.append(c);
    return;
  }

  let view;
  if (S.route.view === "projects") view = viewProjects();
  else if (S.route.view === "types") view = viewCatalog();
  else if (S.route.view === "draft") view = viewDraft(S.route.pid);
  else if (S.route.view === "review") view = viewReview(S.route.pid);
  else if (S.route.view === "sources") view = viewSources(S.route.pid);
  else if (S.route.view === "history") view = viewHistory(S.route.pid);
  else view = viewProjects();

  // 项目内页面始终显示项目名称（已在顶栏面包屑中显示）
  if (S.inspector) {
    const wrap = el("div", "with-insp" + (S.route.view === "draft" ? " draft-with-inspector" : ""));
    wrap.append(view);
    wrap.append(renderInspector());
    stage.append(wrap);
  } else {
    stage.append(view);
  }
  renderInspectorExtra();
  highlightMoney(stage);
  initProseToggles();
  const projectDock = document.querySelector(".project-create-dock");
  if (projectDock) projectDockObserver.observe(projectDock);
  restoreDraftAnchor(anchor);
  if (S.route.view === "draft") requestAnimationFrame(updateDraftDirectory);

}

// 「依据详情」检查器的补充分支挂到 renderInspector 里
function renderInspectorExtra() {
  let spec = S.inspector;
  if (!spec || !["basis", "trace"].includes(spec.kind)) return;
  const box = document.querySelector(".inspector");
  if (!box) return;
  const body = box.querySelector(".ibody");
  const head = box.querySelector(".ihead");
  body.replaceChildren();
  head.replaceChildren();
  const h3 = el("h3");
  const close = el("button", "close"); close.setAttribute("aria-label", "关闭详情"); close.type = "button"; close.textContent = "✕"; close.onclick = closeInspector;
  h3.textContent = spec.kind === "basis" ? "依据版本对比" : "完整追溯路径";
  head.append(h3, close);

  if (spec.kind === "basis") {
    const reviewObject = oOf(spec.review_id);
    const selectedVersion = reviewObject && S.versionOf[reviewObject.id];
    const review = selectedVersion ? revsOf(reviewObject.id).find(r => r.version === selectedVersion) : headRev(reviewObject);
    const changedBases = changedBasisDetails(DATA, review?.block_lineage?.[spec.block_id]?.basis || [spec]);
    // An unchanged intermediary can be stale because of its own historical basis.
    // Select an actual changed upstream item in the existing difference inspector.
    const matching = changedBases.find(b=>b.object_id===spec.object_id && b.revision_id===spec.revision_id && b.item_id===spec.item_id);
    if (!matching && changedBases.length) spec = {...spec,...changedBases[0]};
    if (spec.path?.length) {
      const via=el("p", "tiny muted"); via.textContent="沿已保存依赖追溯："+spec.path.map(p=>typeName(oOf(p.object_id)?.type_key) || p.object_id).join(" → "); body.append(via);
    }
    const ro = oOf(spec.object_id);
    const rev = revOf(spec.revision_id);
    const cur = headRev(ro);
    const comparison = basisStatus(DATA, spec);
    const isStale = comparison === "changed";
    if (!ro) {
      const missing = el("p", "muted"); missing.textContent = "依据对象不存在，无法比较。"; body.append(missing); return;
    }
    if (changedBases.length > 1) {
      const choices = el("div", "review-prompt-actions");
      for (const basis of changedBases) {
        const object = oOf(basis.object_id);
        const revision = revOf(basis.revision_id);
        const item = revision?.payload.items?.find(i => i.item_id === basis.item_id);
        const choice = chipBtn(`${object ? typeName(object.type_key) : basis.object_id} · ${item ? itemLabel(item, object.type_key) : "整对象"}`,
          () => openInspector({ ...spec, ...basis, kind: "basis" }));
        choice.setAttribute("aria-pressed", String(basis.object_id === spec.object_id && basis.item_id === spec.item_id));
        choices.append(choice);
      }
      body.append(choices);
    }
    const comparisonData = compareBasisItems(rev, cur, spec.item_id);
    const intro = el("p", "small");
    intro.textContent = `${typeCode(ro.type_key)} ${typeName(ro.type_key)} · ${isStale ? "依据已变化，成果尚未同步" : comparison === "unknown" ? "缺少依据，无法比较" : "引用内容与当前一致"}`;
    body.append(intro);
    if (comparisonData.removedReference) {
      const note = el("p", "tiny muted");
      note.textContent = "原引用条目已移除；以下展示同一对象的新旧版本变化，新增条目单独标记。";
      body.append(note);
    }
    const pair = el("div", "basis-diff-pair");
    for (const side of ["before", "after"]) {
      const version = side === "before" ? rev : cur;
      const card = el("section", `basis-diff-card ${side}`);
      const header = el("div", "basis-diff-heading");
      const title = el("h4"); title.textContent = side === "before" ? "当前成果采用的依据" : "最新版本的依据";
      header.append(title, tag(version ? `v${version.version}` : "版本缺失", side === "before" ? "red" : "green"));
      card.append(header);
      if (version) {
        const date = el("p", "tiny muted"); date.textContent = `更新于 ${fullTime(version.created_at)}`; card.append(date);
      } else {
        const missing = el("p", "small muted"); missing.textContent = "版本未记录，无法读取内容。"; card.append(missing);
      }
      const sideEntries = (version?.payload.items || []).map(item => comparisonData.items.find(entry => entry.id === item.item_id)).filter(Boolean);
      for (const field of comparisonData.structureFields.filter(f=>f.changed)) {
        const row=el("div", "basis-diff-row changed");
        const sign=el("span", "diff-sign"); sign.textContent=side === "before" ? "−" : "+";
        const key=el("span", "basis-diff-key"); key.textContent=field.key === "title" ? "对象标题" : "条目顺序";
        const content=el("span", "basis-diff-value");
        content.textContent=field.key === "item_order" ? (field[side] || []).map(id=>{const it=version?.payload.items?.find(i=>i.item_id===id);return it?itemLabel(it,ro.type_key):id;}).join(" → ") : field[side] ?? "未记录";
        row.append(sign,key,content); card.append(row);
      }
      for (const entry of sideEntries) {
        const item = entry[side];
        if (!item) continue;
        const unchanged = entry.status === "same";
        const itemBox = el(unchanged ? "details" : "div", `basis-diff-item ${unchanged ? "unchanged" : ""}`);
        const label = el(unchanged ? "summary" : "h5");
        const marker = !comparisonData.available ? "无法比较" : entry.status === "added" ? "+ 新增" : entry.status === "removed" ? "− 移除" : unchanged ? "未变化" : "已修改";
        label.textContent = `${marker} · ${itemLabel(item, ro.type_key)}`;
        itemBox.append(label);
        const fields = el("div", "basis-diff-fields");
        for (const field of entry.fields) {
          const value = field[side];
          if (value === undefined) continue;
          const row = el("div", "basis-diff-row" + (field.changed ? " changed" : ""));
          const key = el("span", "basis-diff-key"); key.textContent = FIELD_LABEL[field.key] || field.key;
          const content = el("span", "basis-diff-value");
          content.textContent = value === null ? "未填写" : typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
          if (["min_minor", "max_minor", "amount_minor"].includes(field.key) && value != null) {
            content.textContent = money(value, item.data.currency) || String(value);
            content.classList.add("money");
          }
          if (field.changed) {
            const sign = el("span", "diff-sign"); sign.textContent = side === "before" ? "−" : "+"; sign.setAttribute("aria-hidden", "true");
            row.append(sign);
          }
          row.append(key, content); fields.append(row);
        }
        itemBox.append(fields);
        const kind = el("div", "basis-diff-meta" + (entry.kindChanged ? " changed" : ""));
        kind.append(epistemicTag(item.epistemic_kind)); itemBox.append(kind);
        if (item.source_refs?.length || entry.sourceChanged) {
          const refs = el("div", "basis-diff-meta" + (entry.sourceChanged ? " changed" : ""));
          refs.append(sourceLinksOf(item));
          if (!item.source_refs?.length) { const p = el("span", "tiny muted"); p.textContent = "此版本未记录来源"; refs.append(p); }
          itemBox.append(refs);
        }
        if (entry.dependenciesChanged && item.dependencies?.length) {
          const deps = el("div", "basis-diff-meta changed");
          for (const dependency of item.dependencies) {
            const p = el("p", "tiny"); const producer = oOf(dependency.producer_object_id);
            p.textContent = `依赖：${producer ? typeName(producer.type_key) : dependency.producer_object_id} · ${dependency.producer_item_id} · ${dependency.producer_revision_id}`;
            deps.append(p);
          }
          itemBox.append(deps);
        }
        card.append(itemBox);
      }
      if (version && !comparisonData.items.some(entry => entry[side])) {
        const p = el("p", "small muted"); p.textContent = "此版本没有对应条目。"; card.append(p);
      }
      pair.append(card);
    }
    body.append(pair);

    const s4 = el("section");
    const t4 = el("h4"); t4.textContent = "操作"; s4.append(t4);
    const row = el("div");
    row.style.cssText = "display:flex;gap:8px;flex-wrap:wrap;";
    row.append(chipBtn("前往该对象", () => go(`#/p/${ro.project_id}/draft/${ro.id}`)));
    s4.append(row);
    body.append(s4);
    const foot = el("div");
    foot.style.cssText = "margin-top:16px;padding-top:12px;border-top:1px solid var(--separator);";
    foot.append(btn("关闭详情", closeInspector, "sm"));
    body.append(foot);
    return;
  }

  // 完整追溯：当前段落 → draft 内容 → 原始来源
  // spec.review_id 是 review 对象 id，需要先解析到正在阅读的那一版
  const reviewObj = oOf(spec.review_id);
  const wantedVer = reviewObj ? S.versionOf[reviewObj.id] : null;
  const rv = reviewObj
    ? (wantedVer ? revsOf(reviewObj.id).find((r) => r.version === wantedVer) || headRev(reviewObj) : headRev(reviewObj))
    : null;
  const blk = rv ? (rv.payload.blocks || []).find((b) => b.block_id === spec.block_id) : null;
  const lg = rv && rv.block_lineage ? rv.block_lineage[spec.block_id] : null;
  const sec = el("section");
  const t = el("h4"); t.textContent = "① 当前段落"; sec.append(t);
  const p = el("div", "small");
  p.style.cssText = "background:var(--bg-grouped);padding:12px 14px;border-radius:10px;";
  p.textContent = blk ? blk.markdown.replace(/\*\*/g, "") : "尚未记录";
  sec.append(p);
  body.append(sec);

  const s2 = el("section");
  const t2 = el("h4"); t2.textContent = "② 使用的 draft 内容"; s2.append(t2);
  if (!lg || !(lg.basis || []).length) {
    const x = el("p", "small muted"); x.textContent = "尚未记录依据。"; s2.append(x);
  }
  for (const b of expandBasis(DATA, lg?.basis || [])) {
    const o = oOf(b.object_id);
    if (!o) {
      const missing = el("p", "small muted"); missing.textContent = `依据对象缺失，无法核对：${b.object_id}`; s2.append(missing); continue;
    }
    const cur = headRev(o);
    const status = basisStatus(DATA, b);
    const stale = status === "changed";
    const row = el("div", "relrow");
    const g = el("div", "grow");
    const top = el("div");
    top.style.cssText = "display:flex;gap:7px;align-items:center;flex-wrap:wrap;";
    top.append(codeChip(typeCode(o.type_key) || "", (themeOf(o.type_key) || {}).hue || "gray"));
    const nm = el("b"); nm.textContent = typeName(o.type_key); top.append(nm);
    if (b.path.length) { const via=el("span", "tiny muted"); via.textContent="经 "+b.path.map(p=>typeName(oOf(p.object_id)?.type_key) || p.object_id).join(" → "); top.append(via); }
    const cited = revOf(b.revision_id);
    top.append(tag(status === "unknown" ? "依据无法核对" : `用 v${cited?.version ?? "?"}` + (stale ? cur?.id === cited?.id ? " · 上游依据已变化" : ` → 现 v${cur?.version ?? "?"}` : ""), status === "unknown" ? "gray" : stale ? "orange" : "green"));
    g.append(top);
    const r2 = revOf(b.revision_id);
    const item = r2 && r2.payload.items ? r2.payload.items.find((x) => x.item_id === b.item_id) : null;
    if (item) {
      const v = el("div", "small"); v.style.marginTop = "6px";
      v.textContent = itemLabel(item, o.type_key);
      g.append(v);
    }
    row.append(g);
    row.append(chipBtn("前往", () => go(`#/p/${o.project_id}/draft/${o.id}`)));
    s2.append(row);
  }
  body.append(s2);

  const s3 = el("section");
  const t3 = el("h4"); t3.textContent = "③ 原始来源"; s3.append(t3);
  const seen = new Set();
  for (const b of expandBasis(DATA, lg?.basis || [])) {
    const r2 = revOf(b.revision_id);
    if (!r2 || !r2.payload.items) continue;
    const items = !b.item_id || b.item_id === "*" ? r2.payload.items : r2.payload.items.filter((x) => x.item_id === b.item_id);
    for (const ref of items.flatMap(item => item.source_refs || [])) {
      if (seen.has(ref.source_version_id)) continue;
      seen.add(ref.source_version_id);
      const row = el("div", "relrow");
      const g = el("div", "grow");
      const k = el("div", "rel-k");
      k.textContent = (DATA.EVIDENCE[ref.evidence_kind] || {}).label || ref.evidence_kind;
      g.append(k);
      const v = el("div"); v.style.marginTop = "5px"; v.append(sourceLink(ref.source_version_id));
      g.append(v);
      if (ref.locator && Object.keys(ref.locator).length) {
        const l = el("div", "tiny muted"); l.style.marginTop = "4px";
        l.textContent = "定位：" + Object.entries(ref.locator).map(([a, b2]) => a + "=" + b2).join(" · ");
        g.append(l);
      }
      row.append(g);
      s3.append(row);
    }
  }
  if (!seen.size) { const x = el("p", "small muted"); x.textContent = "上述条目尚未记录来源定位。"; s3.append(x); }
  body.append(s3);

  const foot = el("div");
  foot.style.cssText = "margin-top:16px;padding-top:12px;border-top:1px solid var(--separator);";
  foot.append(btn("返回阅读", closeInspector, "sm"));
  body.append(foot);
}

function render() { if (DATA) renderStage(); }

let loadGeneration = 0;
async function loadRoute(force=false) {
  const generation = ++loadGeneration;
  const route = parseRoute();
  if (DATA && !force && (DATA.meta.demo || DATA.meta.project_id === route.pid)) {
    render();
  } else {
    const content = el('div','content');
    content.append(empty('◷','正在读取项目内容',['从本机 Yu+ 数据目录读取已保存内容。']));
    $('stage').replaceChildren(content);
    try {
      const loaded = await loadView(route.pid);
      if (generation !== loadGeneration || parseRoute().pid !== route.pid) return;
      DATA = loaded;
      DATA.meta.project_id = route.pid;
      localFileCapabilities = undefined;
      pageLoadedAt = new Date();
      render();
    } catch (error) {
      if (generation !== loadGeneration) return;
      const failure = el('div','content');
      failure.append(empty('!','无法读取项目内容',[error.message,'请确认本地服务地址及数据目录；读取失败不表示项目为空。']));
      failure.append(btn('重新读取',()=>loadRoute(true)));
      $('stage').replaceChildren(failure);
      // Retain navigation, but never render a different project's cached data.
      DATA = undefined;
      return;
    }
  }
  if (S.route?.view === 'draft' && S.route.objId) scrollToDraft(S.route.objId);
  else window.scrollTo({top:0});
}

window.addEventListener("hashchange", () => {
  S.inspector = null;
  document.body.classList.remove("navigation-open");
  loadRoute();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.body.classList.remove("navigation-open");
    document.querySelector(".mobile-menu")?.setAttribute("aria-expanded", "false");
    if (S.inspector) closeInspector();
  }
});
loadRoute();

// Keep an open version menu attached to its trigger by dismissing it when the reading surface moves.
const dismissVersionMenus = (event) => {
  for (const menu of document.querySelectorAll(".version-menu:popover-open")) {
    if (!(event.target instanceof Node) || !menu.contains(event.target)) menu.hidePopover();
  }
};
document.addEventListener("scroll", dismissVersionMenus, { capture:true, passive:true });
window.addEventListener("resize", dismissVersionMenus);
