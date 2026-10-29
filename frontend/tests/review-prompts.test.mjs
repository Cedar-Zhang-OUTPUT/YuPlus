import test from 'node:test';
import assert from 'node:assert/strict';
import DATA from '../public/data/demo.js';
import { reviewContext, reviewExportPrompt, reviewUpdatePrompt } from '../public/data/review-prompts.js';

test('export includes all current review instances, shared Q&A, and exact source snapshots', () => {
  const c = reviewContext(DATA, 'prj_city');
  assert.deepEqual(new Set(c.documents.map(d => d.object_id)), new Set(['obj_r01','obj_r02','obj_r03','obj_qa']));
  assert.ok(c.objects.every(o => o.project_id === 'prj_city'));
  assert.ok(c.revisions.some(r => r.id === 'rev_deliv_1'));
  assert.ok(c.revisions.some(r => r.id === 'rev_deliv_2'));
  assert.ok(c.source_versions.some(s => s.body_text));
  for (const r of c.revisions) for (const item of r.payload.items || []) {
    for (const ref of item.source_refs || []) assert.ok(c.source_versions.some(s => s.id === ref.source_version_id));
  }
  assert.deepEqual(c.missing_evidence, []);
});

test('update focuses one review and distinguishes changed items from unchanged siblings', () => {
  const c = reviewContext(DATA, 'prj_city', 'obj_r01');
  assert.deepEqual(c.documents.map(d => d.object_id), ['obj_r01']);
  const checks = c.documents[0].basis_checks.flatMap(b => b.basis);
  assert.ok(checks.some(b => b.item_id === 'deliv_r1_film' && b.status === 'changed'));
  assert.ok(checks.some(b => b.status === 'same'));
  assert.match(reviewUpdatePrompt(DATA, 'prj_city', 'obj_r01'), /不要修改既有历史版本/);
  assert.match(reviewExportPrompt(DATA, 'prj_city'), /新的飞书文档/);
  assert.match(reviewExportPrompt(DATA, 'prj_city'), /前端模拟数据/);
});

test('missing evidence is reported, and production prompts use CLI instead of fixture writes', () => {
  const data = structuredClone(DATA);
  delete data.indexes.svById.sv_oral_budget_1;
  data.meta.demo = false;
  assert.ok(reviewContext(data, 'prj_city').missing_evidence.includes('source_version:sv_oral_budget_1'));
  const prompt = reviewUpdatePrompt(data, 'prj_city', 'obj_r01');
  assert.match(prompt, /review prepare/);
  assert.match(prompt, /review publish/);
  assert.doesNotMatch(prompt, /更新前端模拟成果/);
  assert.throws(() => reviewContext(DATA, 'prj_city', 'obj_qa'), /成果不存在/);
});

test('export prompt stays short regardless of project size and routes to the export skill',()=>{
  const data={projects:[{id:'prj_1',name:'项目'}],meta:{demo:false,data_dir:'/data/我的项目'},objects:null};
  const text=reviewExportPrompt(data,'prj_1');
  assert.ok(text.length<300);
  assert.match(text,/references\/export.md/);
  assert.match(text,/保存导出记录/);
  assert.match(text,/"project_id":"prj_1"/);
  assert.match(text,/"data_dir":"\/data\/我的项目"/);
  assert.doesNotMatch(text,/<yuplus-context>|documents|revisions/);
});
