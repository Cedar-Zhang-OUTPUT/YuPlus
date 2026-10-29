import test from 'node:test';
import assert from 'node:assert/strict';
import {folderUrl, websiteUrl, libraryPrompt, libraryRemovalPrompt, libraryView, saveLibraryRequest} from '../public/data/case-library.js';
const url='https://example.feishu.cn/drive/folder/FolderOne';

test('case library requires an HTTPS Feishu folder and canonicalizes share URLs',()=>{
  for (const bad of ['', ' ', null, 'javascript:alert(1)', 'https://feishu.cn.evil.com/drive/folder/a',
    'https://example.feishu.cn/docx/a','https://user@example.feishu.cn/drive/folder/a',url+'\\x']) {
    assert.equal(folderUrl(bad),null);assert.equal(libraryPrompt(bad),null);
  }
  assert.equal(folderUrl(' '+url+'/?from=share '),url);
  assert.equal(folderUrl('https://example.larksuite.com/folder/a'),'https://example.larksuite.com/drive/folder/a');
  assert.ok(libraryPrompt(url).includes(url));
  assert.ok(libraryPrompt(url).includes('本次只登记案例库源'));
});

test('website registration has an independent required prompt and titled website cards',()=>{
  for(const bad of ['', 'javascript:alert(1)', 'file:///tmp/a', 'https://user:pass@example.com', 'https://bad host/']) {
    assert.equal(websiteUrl(bad),null);assert.equal(libraryPrompt(bad,'website'),null);
  }
  const site='https://example.com/cases/?tag=art#one';
  assert.equal(websiteUrl('https://EXAMPLE.com:443/cases/?tag=art#one'),site);
  assert.equal(websiteUrl('http://example.com'),'http://example.com/');
  assert.ok(libraryPrompt(site,'website').includes('kind=website'));
});

function fakeDOM() {
  const old = globalThis.document;
  globalThis.document = {createElement: tag => ({tag, children: [], attrs: {}, dataset: {}, value: '', textContent: '',
    append(...nodes) { this.children.push(...nodes); }, replaceChildren(...nodes) {this.children = nodes;},
    setAttribute(k, v) {this.attrs[k] = v;}, focus() {}, querySelector() {return null;}})};
  return () => {globalThis.document = old;};
}
const nodes = root => [root, ...root.children.flatMap(nodes)];

test('catalog keeps disabled sources visible, filters tabs/search, and persists toggles', async () => {
  const cleanup = fakeDOM();
  globalThis.CSS ||= {escape: value => value};
  try {
    let rows = [{id:'one', origin:'official', name:'Official One', kind:'website', url:'https://one.example/', version:1},
      {id:'two', origin:'official', name:'Official Two', kind:'website', url:'https://two.example/', version:2, deleted_at:'now'},
      {id:'own', origin:'personal', name:'My source', kind:'website', url:'https://mine.example/', version:1}];
    const calls = [], state = {};
    const page = libraryView(rows, state, {save: async request => {
      calls.push(request); rows = rows.map(r => r.id === request.input.library_id ? {...r, deleted_at:null, version:r.version+1} : r); return rows;
    }});
    assert.equal(nodes(page).filter(n => n.tag === 'article').length, 2);
    await nodes(page).find(n => n.attrs['aria-label'] === '添加 Official Two').onclick();
    assert.equal(calls[0].action, 'restore'); assert.equal(calls[0].input.base_version, 2);
    assert.ok(nodes(page).some(n => n.attrs['aria-label'] === '移除 Official Two'));
    const search = nodes(page).find(n => n.type === 'search'); search.value = 'One'; search.oninput();
    assert.equal(nodes(page).filter(n => n.tag === 'article').length, 1);
    search.value = ''; search.oninput();
    nodes(page).find(n => n.tag === 'button' && n.textContent.startsWith('Personal')).onclick();
    assert.equal(nodes(page).filter(n => n.tag === 'article').length, 1);
    assert.ok(nodes(page).some(n => n.tag === 'a' && n.textContent === 'My source'));
  } finally {cleanup();}
});

test('personal form validates input and retries uncertain writes with the same request ID', async () => {
  const cleanup = fakeDOM();
  try {
    const requests = []; let result;
    const page = libraryView([], {}, {save: async request => {
      requests.push(request); if (requests.length === 1) throw new Error('Network failed');
      return [{id:'own', origin:'personal', name:'My site', url:'https://example.com/', kind:'website', version:1}];
    }, onChange: rows => {result = rows;}});
    const all = nodes(page), form = all.find(n => n.tag === 'form');
    const name = all.find(n => n.id === 'library-name'), url = all.find(n => n.id === 'library-url');
    name.value = 'My site'; url.value = 'javascript:bad'; url.oninput();
    await form.onsubmit({preventDefault(){}}); assert.equal(requests.length, 0);
    url.value = 'https://example.com'; url.oninput();
    await form.onsubmit({preventDefault(){}});
    assert.ok(nodes(page).some(n => n.textContent === 'Network failed'));
    await form.onsubmit({preventDefault(){}});
    assert.equal(requests.length, 2); assert.equal(requests[0].request_id, requests[1].request_id);
    assert.deepEqual(requests[1].input, {kind:'website', name:'My site', url:'https://example.com/'});
    assert.equal(result[0].origin, 'personal'); assert.ok(form.hidden);
  } finally {cleanup();}
});

test('HTTP writes expose failures rather than optimistic success', async () => {
  const request = {action:'delete', input:{library_id:'one', base_version:1}, request_id:'ui_test'};
  let args;
  await assert.rejects(saveLibraryRequest(request, async (...values) => {
    args = values; return {ok:false, json:async () => ({ok:false, error:{message:'版本已变化'}})};
  }), /版本已变化/);
  assert.equal(args[0], '/api/libraries'); assert.equal(args[1].method, 'POST');
  assert.deepEqual(JSON.parse(args[1].body), request);
});
