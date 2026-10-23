import test from 'node:test';
import assert from 'node:assert/strict';
import {logoPrompt,initLogoMenu} from '../public/data/logo.js';

test('avatar instruction requires a live data directory and never writes a project',()=>{
  assert.equal(logoPrompt({meta:{demo:true}}),null);
  assert.equal(logoPrompt({}),null);
  const prompt=logoPrompt({meta:{demo:false,data_dir:'/tmp/Yu+ 工作'}});
  assert.match(prompt,/\/tmp\/Yu\+ 工作/);assert.match(prompt,/若尚未附图/);
  assert.match(prompt,/压缩/);assert.match(prompt,/不修改项目内容/);
});

test('avatar menu supports hover, keyboard, escape, scoped copying and default fallback',()=>{
  function node(){return {events:{},attrs:{},classList:{toggle(){}},addEventListener(k,fn){this.events[k]=fn},setAttribute(k,v){this.attrs[k]=v},getAttribute(k){return this.attrs[k]},removeAttribute(k){delete this.attrs[k]},focus(){document.activeElement=this}};}
  const root=node(),trigger=node(),panel=node(),copy=node(),img=node(),fallback=node(),outside=node();
  root.querySelector=s=>({'.logo-trigger':trigger,'.logo-menu':panel,'.logo-change':copy})[s];
  trigger.querySelector=s=>s==='img'?img:fallback;
  root.contains=n=>[root,trigger,panel,copy,img,fallback].includes(n);
  const previous=globalThis.document;
  globalThis.document=node();document.activeElement=outside;
  let data={meta:{demo:false,data_dir:'/tmp/one'},logo:{custom:true,url:'/api/logo?v=1'}};
  const copies=[];
  try {
    const update=initLogoMenu(root,()=>data,text=>copies.push(text));update();
    assert.equal(panel.inert,true);assert.equal(img.src,'/api/logo?v=1');assert.equal(fallback.hidden,true);
    root.events.mouseenter();assert.equal(trigger.attrs['aria-expanded'],'true');assert.equal(panel.inert,false);
    root.events.mouseleave();assert.equal(panel.inert,true);
    trigger.events.click();assert.equal(panel.inert,false);
    root.events.keydown({key:'ArrowDown',target:trigger,preventDefault(){}});assert.equal(document.activeElement,copy);
    copy.events.click();assert.deepEqual(copies,[logoPrompt(data)]);
    root.events.keydown({key:'Escape',stopPropagation(){}});assert.equal(panel.inert,true);assert.equal(document.activeElement,trigger);
    root.events.focusin();assert.equal(panel.inert,true);
    root.events.mouseenter();document.events.pointerdown({target:outside});assert.equal(panel.inert,true);
    data={meta:{demo:false,data_dir:'/tmp/two'},logo:{custom:false}};update();assert.equal(img.hidden,true);assert.equal(fallback.hidden,false);
    copy.events.click();assert.equal(copies[1],logoPrompt(data));
    data={meta:{demo:true}};update();assert.equal(copy.disabled,true);copy.events.click();assert.equal(copies.length,2);
    img.events.error();assert.equal(fallback.hidden,false);
  } finally {globalThis.document=previous;}
});
