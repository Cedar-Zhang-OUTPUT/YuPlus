import test from 'node:test';
import assert from 'node:assert/strict';
import {folderUrl, websiteUrl, libraryPrompt, libraryRemovalPrompt, libraryView} from '../public/data/case-library.js';
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

test('required input gates copying, rechecks current value, and preserves editable state',()=>{
  const previous=globalThis.document;
  globalThis.document={createElement:tag=>({tag,children:[],attrs:{},append(...nodes){this.children.push(...nodes)},setAttribute(k,v){this.attrs[k]=v}})};
  const nodes=root=>[root,...root.children.flatMap(nodes)];
  try {
    const copies=[],state={};const page=libraryView([],state,text=>copies.push(text),s=>s);
    const all=nodes(page);const input=all.find(n=>n.tag==='input');const button=all.find(n=>n.tag==='button');
    assert.ok(button.disabled);assert.ok(input.required);
    button.onclick();assert.deepEqual(copies,[]);
    input.value='https://example.feishu.cn/docx/abc';input.oninput();
    assert.ok(button.disabled);assert.equal(input.attrs['aria-invalid'],'true');
    input.value=url;input.oninput();assert.equal(button.disabled,false);
    button.onclick();assert.deepEqual(copies,[libraryPrompt(url)]);assert.equal(state.url,url);
    input.value=' ';button.onclick();assert.equal(copies.length,1);assert.ok(button.disabled);
    const removals=[];
    const cards=nodes(libraryView([{id:'lib',name:'<标题>',url,created_at:'2026-10-23'},{name:'已移除',url,deleted_at:'now'}],{},text=>removals.push(text),s=>s));
    assert.equal(cards.filter(n=>n.tag==='article').length,1);
    const link=cards.find(n=>n.tag==='a');assert.equal(link.href,url);assert.equal(link.target,'_blank');
    assert.equal(link.rel,'noopener noreferrer');
    const remove=cards.find(n=>n.tag==='button' && n.textContent==='复制移除 Prompt');
    assert.deepEqual(removals,[]);remove.onclick();
    assert.equal(removals[0],libraryRemovalPrompt({id:'lib',name:'<标题>'}));
    assert.ok(removals[0].includes('不删除飞书文件夹'));
    assert.ok(removals[0].includes('library_id：lib'));

    assert.equal(cards.find(n=>n.tag==='h3').children[0],link);
    assert.equal(link.textContent,'<标题>');
    assert.ok(!cards.some(n=>n.textContent===url || n.textContent==='打开文件夹 ↗'));
    const invalid=nodes(libraryView([{name:'无效链接案例库',url:'javascript:alert(1)',created_at:'2026-10-23'}],{},()=>{},s=>s));
    assert.ok(!invalid.some(n=>n.tag==='a'));
    assert.equal(invalid.find(n=>n.tag==='h3').textContent,'无效链接案例库');
  } finally {globalThis.document=previous;}
});


test('website registration has an independent required prompt and titled website cards',()=>{
  for(const bad of ['', 'javascript:alert(1)', 'file:///tmp/a', 'https://user:pass@example.com', 'https://bad host/']) {
    assert.equal(websiteUrl(bad),null);assert.equal(libraryPrompt(bad,'website'),null);
  }
  const site='https://example.com/cases/?tag=art#one';
  assert.equal(websiteUrl('https://EXAMPLE.com:443/cases/?tag=art#one'),site);
  assert.equal(websiteUrl('http://example.com'),'http://example.com/');
  assert.ok(libraryPrompt(site,'website').includes('kind=website'));
  const prev=globalThis.document;
  globalThis.document={createElement:tag=>({tag,children:[],attrs:{},append(...nodes){this.children.push(...nodes)},setAttribute(k,v){this.attrs[k]=v}})};
  const nodes=root=>[root,...root.children.flatMap(nodes)];
  try {
    const copied=[],state={url};
    const all=nodes(libraryView([{id:'web',kind:'website',name:'网站案例',url:site}],state,text=>copied.push(text),s=>s));
    const inputs=all.filter(n=>n.tag==='input');assert.equal(inputs.length,2);
    const website=inputs.find(n=>n.id==='library-website-url');
    const button=all.find(n=>n.textContent==='复制新增网站 Prompt');
    assert.ok(button.disabled);website.value=site;website.oninput();assert.equal(button.disabled,false);
    button.onclick();assert.equal(copied[0],libraryPrompt(site,'website'));
    assert.equal(state.url,url);assert.equal(state.websiteUrl,site);
    website.value='';button.onclick();assert.equal(copied.length,1);
    const link=all.find(n=>n.tag==='a');assert.equal(link.href,site);assert.equal(link.textContent,'网站案例');assert.equal(link.target,'_blank');
    assert.ok(all.some(n=>n.textContent==='网站'));
    assert.ok(libraryRemovalPrompt({id:'web',kind:'website',name:'网站案例'}).includes('不删除网站或网站内容'));
  } finally {globalThis.document=prev;}
});
