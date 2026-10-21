import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {hydrateView} from '../public/data/runtime.js';
import {openQuestionState} from '../public/data/selectors.js';
import DATA from '../public/data/demo.js';
const catalog=JSON.parse(await readFile(new URL('../../src/yuplus/contracts/object-types.json',import.meta.url),'utf8'));
test('live and preview catalogs expose open questions in judgment, separately from shared QA',()=>{
  const live=hydrateView({meta:{demo:false},projects:[],catalog,objects:[],object_revisions:[],sources:[],source_versions:[]});
  for(const data of [live,DATA]){
    assert.equal(data.catalog.find(t=>t.type_key==='open_questions').code,'D24');
    assert.ok(data.THEMES.find(t=>t.key==='judgment').types.includes('open_questions'));
    assert.equal(data.REVIEW_KINDS.find(t=>t.code==='R05').type_key,'qa_view');
    assert.ok(!data.REVIEW_KINDS.some(t=>t.type_key==='open_questions'));
  }
});
test('open question statuses distinguish exploration and conclusions without claiming customer answers',()=>{
  assert.equal(openQuestionState('open').label,'待讨论');
  assert.equal(openQuestionState('exploring').label,'探索中');
  assert.equal(openQuestionState('resolved').label,'已有结论');
  assert.equal(openQuestionState('deferred').label,'暂缓');
  assert.equal(openQuestionState(undefined).label,'未记录状态');
});
