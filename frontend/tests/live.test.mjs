import test from 'node:test';
import assert from 'node:assert/strict';
import { loadView, hydrateView } from '../public/data/runtime.js';
import { basisStatus } from '../public/data/selectors.js';
import { reviewUpdatePrompt, reviewExportPrompt } from '../public/data/review-prompts.js';

const raw = () => ({meta:{demo:false,data_dir:'/tmp/real-projects'},projects:[{id:'p',name:'真实项目'}],
  catalog:[],internal_types:[],project_activity:{},objects:[{id:'o',project_id:'p',type_key:'debrief',layer:'review',current_revision_id:'r',scope_key:'project'}],
  object_revisions:[{id:'r',object_id:'o',payload:{title:'成果',blocks:[{block_id:'b',markdown:'真实内容'}]},block_lineage:{}}],
  sources:[],source_versions:[],changes:[],decisions:[],review_checks:[],exports:[],basis_status_by_key:{'d:old:i':'changed'}});

test('live view is project scoped and hydrates without demo fallback', async () => {
  const urls=[];
  const data=await loadView('p',async url=>{urls.push(url);return {ok:true,json:async()=>url==='/api/health'?{mode:'live'}:raw()};});
  assert.deepEqual(urls,['/api/health','/api/view?project=p']);
  assert.equal(data.indexes.objById.o.project_id,'p');
  assert.equal(data.meta.demo,false);
  assert.equal(data.THEMES.length,4);
});
test('failed API and corrupt response reject instead of showing demo or empty project',async()=>{
  await assert.rejects(loadView('p',async()=>({ok:false,status:503})),/503/);
  assert.throws(()=>hydrateView({}),/数据/);
});
test('real basis follows backend authority and missing authority is unknown',()=>{
  const data=hydrateView(raw());
  assert.equal(basisStatus(data,{object_id:'d',revision_id:'old',item_id:'i'}),'changed');
  assert.equal(basisStatus(data,{object_id:'d',revision_id:'old',item_id:'x'}),'unknown');
});
test('production prompts bind real data directory and versions without embedding whole body',()=>{
  const data=hydrateView(raw());
  for(const prompt of [reviewUpdatePrompt(data,'p','o'),reviewExportPrompt(data,'p')]){
    assert.ok(prompt.includes('/tmp/real-projects'));
    assert.ok(!prompt.includes('frontend/public/data/demo.js'));
    assert.ok(!prompt.includes('真实内容'));
  }
  assert.match(reviewUpdatePrompt(data,'p','o'),/review prepare/);
  assert.ok(reviewUpdatePrompt(data,'p','o').includes('"revision_id": "r"'));
  assert.ok(reviewExportPrompt(data,'p').length<300);
});

test('Q&A uses persisted statuses without assuming a closed question was answered',async()=>{
  const {qaState}=await import('../public/data/selectors.js');
  assert.deepEqual(qaState('answered'),{label:'已答复',hue:'green',answered:true});
  assert.equal(qaState('closed').answered,false);
  assert.equal(qaState('open').label,'待答复');
  assert.equal(qaState(undefined).label,'未记录状态');
});
test('export excludes deleted Review roots while historical records stay accessible',()=>{
  const snapshot=raw();snapshot.objects[0].archived_at='2026-10-22';
  const data=hydrateView(snapshot);
  assert.equal(data.indexes.objById.o.id,'o');
  assert.throws(()=>reviewUpdatePrompt(data,'p','o'),/成果不存在/);
  assert.ok(!reviewExportPrompt(data,'p').includes('"object_id": "o"'));
});
