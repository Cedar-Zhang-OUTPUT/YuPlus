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
    const all=nodes(panel), button=all.find(n=>n.tag==='button'), status=all.find(n=>n.attrs.role==='status');
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
    const all=nodes(panel), button=all.find(n=>n.tag==='button'), status=all.find(n=>n.attrs.role==='status');
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
