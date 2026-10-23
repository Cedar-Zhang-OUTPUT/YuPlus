import test from 'node:test';
import assert from 'node:assert/strict';
import {loadingProgress} from '../public/data/loading-progress.js';

test('mock loading stays incomplete until success and releases timers when replaced',async t=>{
 const old=globalThis.document;
 globalThis.document={createElement:tag=>({tag,style:{},attrs:{},children:[],append(...nodes){this.children.push(...nodes)},setAttribute(k,v){this.attrs[k]=v}})};
 t.mock.timers.enable({apis:['setInterval','setTimeout','Date'],now:1000});
 try{
  const progress=loadingProgress(),track=progress.element.children[1],fill=track.children[0];
  assert.equal(track.attrs.role,'progressbar');assert.equal(track.attrs['aria-valuenow'],undefined);
  t.mock.timers.tick(60000);
  assert.notEqual(fill.style.transform,'scaleX(1)');
  const completion=progress.finish();assert.equal(fill.style.transform,'scaleX(1)');
  progress.stop();await completion;
  const next=loadingProgress(),nextFill=next.element.children[1].children[0];
  next.stop();const before=nextFill.style.transform;t.mock.timers.tick(60000);
  assert.equal(nextFill.style.transform,before);
  assert.equal(fill.style.transform,'scaleX(1)');
 }finally{t.mock.timers.reset();globalThis.document=old;}
});
