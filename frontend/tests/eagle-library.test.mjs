import test from 'node:test';
import assert from 'node:assert/strict';
import {eagleLibraryEntry, EAGLE_CONNECT_PROMPT} from '../public/data/eagle-library.js';

function fakeDOM() {
  const previous = globalThis.document;
  globalThis.document = {createElement: tag => ({tag, children:[], attrs:{}, textContent:'',
    append(...children) {this.children.push(...children);},
    setAttribute(key,value) {this.attrs[key]=value;},
    focus() {this.focused=true;}, select() {this.selected=true;}})};
  return () => {globalThis.document=previous;};
}
const nodes = root => [root,...root.children.flatMap(nodes)];

test('connect copies a short Skill invocation without claiming a connection or saving configuration', async () => {
  const cleanup = fakeDOM();
  try {
    const copies=[];
    const panel=eagleLibraryEntry({copy:async text=>copies.push(text)});
    const all=nodes(panel), button=all.find(n=>n.tag==='button'), status=all.find(n=>n.className==='eagle-library-status');
    assert.equal(status.textContent,'');
    await button.onclick();
    assert.deepEqual(copies,['使用 $yuplus 连接 Eagle 案例库。']);
    assert.match(status.textContent,/已复制/);
    assert.doesNotMatch(status.textContent,/已连接|连接成功|验证完成|配置已写入/);
    assert.equal(all.filter(n=>n.tag==='textarea').length,1);
    assert.equal(all.find(n=>n.tag==='textarea').readOnly,true);
    assert.equal(button.disabled,false);
  } finally {cleanup();}
});

test('missing or denied clipboard offers selectable text and retry recovers without leaking errors', async () => {
  const cleanup = fakeDOM();
  try {
    let attempts=0;
    const panel=eagleLibraryEntry({copy:async()=>{if(++attempts===1)throw new Error('private environment detail');}});
    const all=nodes(panel), button=all.find(n=>n.tag==='button'), status=all.find(n=>n.className==='eagle-library-status');
    const fallback=all.find(n=>n.className==='eagle-library-fallback'), prompt=all.find(n=>n.tag==='textarea');
    await button.onclick();
    assert.equal(fallback.hidden,false);assert.equal(prompt.value,EAGLE_CONNECT_PROMPT);
    assert.equal(prompt.focused,true);assert.equal(prompt.selected,true);
    assert.match(status.textContent,/未能自动复制/);assert.doesNotMatch(status.textContent,/private environment detail/);
    assert.equal(button.disabled,false);
    await button.onclick();assert.equal(attempts,2);assert.equal(fallback.hidden,true);assert.match(status.textContent,/已复制/);
  } finally {cleanup();}
});

test('repeated click while clipboard is pending does not dispatch another operation', async () => {
  const cleanup = fakeDOM();
  try {
    let resolveCopy,calls=0;
    const panel=eagleLibraryEntry({copy:()=>{calls++;return new Promise(resolve=>{resolveCopy=resolve;});}});
    const button=nodes(panel).find(n=>n.tag==='button');
    const pending=button.onclick();assert.equal(button.disabled,true);
    await button.onclick();assert.equal(calls,1);
    resolveCopy();await pending;assert.equal(button.disabled,false);
  } finally {cleanup();}
});

import {eagleStatusText, watchEagleStatus} from '../public/data/eagle-library.js';

test('connection observation shows identity and coverage but expires without pretending to probe MCP', () => {
  const observed = Date.parse('2026-11-04T10:00:00Z');
  const record = {state:'verified', library_name:'品牌案例', observed_at:new Date(observed).toISOString(), material_read:'thumbnail'};
  assert.match(eagleStatusText(record, observed).label, /已连接/);
  assert.match(eagleStatusText(record, observed).detail, /品牌案例.*缩略图可读.*最近检查/);
  assert.equal(eagleStatusText(record, observed + 25*60*60*1000).label, '连接待复核');
  assert.equal(eagleStatusText({...record, state:'unavailable'}, observed).label, '连接不可用');
  assert.equal(eagleStatusText({...record, state:'waiting'}, observed).connected, false);
  assert.match(eagleStatusText(undefined).label, /尚未记录/);
});

test('connected card preserves observed success when copying reverify and carries workspace context', async () => {
  const cleanup = fakeDOM();
  try {
    let copied;
    const panel = eagleLibraryEntry({record:{version:1, state:'verified', library_name:'真实库名', observed_at:new Date().toISOString(), material_read:'original'}, dataDir:'/workspace/a b', copy:async text=>{copied=text;}});
    const all=nodes(panel), button=all.find(n=>n.tag==='button');
    assert.equal(button.textContent,'重新验证连接');
    assert.match(all.find(n=>n.className==='eagle-library-details').textContent,/真实库名.*原文件可读/);
    await button.onclick();
    assert.match(copied,/"\/workspace\/a b"/);
    assert.match(all.find(n=>n.className.includes('eagle-library-badge')).textContent,/已连接/);
  } finally {cleanup();}
});

test('poll refresh observes transitions, skips hidden pages and cancels in-flight updates on navigation', async () => {
  let next, resolve, signal, visible=true, calls=0, failures=0; const updates=[];
  const stop=watchEagleStatus({load:s=>{calls++; signal=s; return new Promise(r=>{resolve=r;});}, update:r=>updates.push(r), failed:()=>failures++, visible:()=>visible, schedule:fn=>{next=fn;return 1;}, cancel:()=>{next=null;}});
  resolve({state:'verified'}); await Promise.resolve(); await Promise.resolve();
  assert.deepEqual(updates,[{state:'verified'}]);
  visible=false; await next(); assert.equal(calls,1);
  visible=true; const pending=next(); assert.equal(calls,2);
  stop(); assert.equal(signal.aborted,true);
  resolve({state:'unavailable'}); await pending;
  assert.equal(updates.length,1); assert.equal(failures,0); assert.equal(next,null);
});

test('failed poll reports an unavailable status read and subsequent successful poll recovers', async () => {
  let next, attempt=0, failures=0; const updates=[];
  const stop=watchEagleStatus({load:async()=>{if(++attempt===1)throw new Error('private');return {state:'connected'};}, update:r=>updates.push(r), failed:()=>failures++, visible:()=>true, schedule:fn=>{next=fn;}, cancel:()=>{}});
  await Promise.resolve(); await Promise.resolve(); assert.equal(failures,1);
  await next(); assert.deepEqual(updates,[{state:'connected'}]); stop();
});
