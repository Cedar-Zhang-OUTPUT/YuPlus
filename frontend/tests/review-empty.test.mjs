import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {REVIEW_KINDS} from '../public/data/vocabulary.js';

const app=await readFile(new URL('../public/app.js',import.meta.url),'utf8');
const renderer=app.slice(app.indexOf('function viewReview('),app.indexOf('function instanceLabel('));
function element(tag='div') {
  return {tag,children:[],style:{setProperty(){}},classList:{add(){}},attrs:{},
    setAttribute(k,v){this.attrs[k]=v;},append(...nodes){this.children.push(...nodes);}};
}
function text(node){return (node.textContent||'')+node.children.map(text).join(' ');}
function buttons(node){return [...(node.tag==='button'?[node]:[]),...node.children.flatMap(buttons)];}
function setup(objects=[]) {
  const S={route:{objId:null}};
  const context=vm.createContext({S,DATA:{REVIEW_KINDS,objects,exports:[]},el:element,
    projOf:()=>({name:'测试项目'}),hueOf:x=>x,
    btn:(label,onclick)=>Object.assign(element('button'),{textContent:label,onclick}),
    projectMonitorPanel:()=>Object.assign(element(),{textContent:'监控群聊'}),
    empty:(_icon,label)=>Object.assign(element(),{textContent:label}),
    reviewDocument:o=>Object.assign(element(),{textContent:'已有成果正文 '+o.id}),
    qaReviewView:()=>Object.assign(element(),{textContent:'客户 Q&A'}),
    go:hash=>{S.route.objId=hash.split('/').at(-1);},
  });
  vm.runInContext(renderer,context);
  return {S,render:()=>context.viewReview('p')};
}
for(const kind of REVIEW_KINDS.filter(k=>k.persistable)) {
  test(`empty ${kind.code} keeps the review shell and all category navigation`,()=>{
    const env=setup();env.S.route.objId=kind.type_key;
    const page=env.render();const visible=text(page);
    assert.ok(visible.includes('整理与Review'));
    assert.ok(visible.includes('监控群聊'));
    assert.ok(visible.includes('尚未生成 '+kind.name));
    for(const category of REVIEW_KINDS)assert.ok(buttons(page).some(b=>text(b).includes(category.name)));
    assert.equal(buttons(page).find(b=>text(b).includes(kind.name)).attrs['aria-current'],'true');
  });
}
test('empty categories can switch directly back to a populated review without using the dock',()=>{
  const env=setup([{id:'obj_debrief',project_id:'p',layer:'review',type_key:'debrief',current_revision_id:'rev1'}]);
  for(const kind of REVIEW_KINDS.filter(k=>['creative_review','creator_brief'].includes(k.type_key))) {
    let page=env.render();assert.ok(text(page).includes('已有成果正文 obj_debrief'));
    buttons(page).find(b=>text(b).includes(kind.name)).onclick();
    page=env.render();assert.ok(text(page).includes('尚未生成 '+kind.name));
    assert.ok(!text(page).includes('已有成果正文'));
    buttons(page).find(b=>text(b).includes('主策 Debrief')).onclick();
    assert.ok(text(env.render()).includes('已有成果正文 obj_debrief'));
  }
});
test('deleted review is hidden while an old route keeps the category shell',()=>{
  const env=setup([{id:'deleted',project_id:'p',layer:'review',type_key:'debrief',current_revision_id:'r',archived_at:'2026-10-22'}]);
  env.S.route.objId='deleted';
  const page=env.render();
  assert.ok(!text(page).includes('已有成果正文'));
  assert.ok(text(page).includes('尚未生成 主策 Debrief'));
  assert.ok(buttons(page).some(b=>text(b).includes('主策 Debrief') && text(b).includes('暂无')));
});
