import test from 'node:test';
import assert from 'node:assert/strict';
import {caseVersions,caseFindingPrompt,secondTime,setBoardLink,originalUrl} from '../public/data/case-finding.js';
import {createPreviewController,previewUrl,previewTransport} from '../public/data/case-preview.js';
const a={id:'a',project_id:'p',version:1,board_token:'board_a'},b={id:'b',project_id:'p',version:2,board_token:'board_b'};
const packet=id=>({version_id:id,image_url:'/api/case-finding/images/'+id,fetched_at:'2026-10-23T03:12:34Z'});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(fetchPreview,loadImage=async()=>({width:1200,height:720})){
 const states=[],timers=new Map();let timer=0;
 const c=createPreviewController({fetchPreview,loadImage,onState:s=>states.push(s),setTimer:(f,ms)=>{timers.set(++timer,{f,ms});return timer;},clearTimer:id=>timers.delete(id)});
 return {c,states,timers};
}
test('version list is project-scoped, sorted and timestamp precision is seconds',()=>{
 assert.deepEqual(caseVersions({case_findings:[a,{...b,project_id:'other'},b]},'p'),[b,a]);
 assert.match(secondTime('2026-10-23T03:12:34Z'),/^2026-10-23 \d\d:12:34$/);assert.equal(secondTime(null),'—');
 const prompt=caseFindingPrompt({id:'p',name:'城市记忆'},{meta:{demo:false,data_dir:'/tmp/data'}});
 assert.match(prompt,/开启一轮新的找案例研究/);assert.match(prompt,/不要覆盖或续改已有研究/);assert.match(prompt,/project_id：p/);assert.match(prompt,/\/tmp\/data/);assert.doesNotMatch(prompt,/draft|review|source/);
});
test('preview URLs are local and sample images only allowed in explicit demo',()=>{
 for(const url of ['https://external.test/a.png','//external.test/a','/api/assets','/api/case-finding/images/../../bad','javascript:x','data:x'])assert.equal(previewUrl(url),null);
 assert.equal(previewUrl('/demo/case-board-v1.svg'),null);assert.equal(previewUrl('/demo/case-board-v1.svg',true),'/demo/case-board-v1.svg');
 assert.equal(previewTransport({meta:{demo:false}},'p'),null);
});
test('switching versions cancels older work; hidden and destroyed views stop refreshing',async()=>{
 const pending=[];const {c,states,timers}=fixture((record,signal)=>new Promise(resolve=>pending.push({record,signal,resolve})));
 c.select(a);c.select(b);assert.equal(pending[0].signal.aborted,true);
 pending[1].resolve(packet('b'));await flush();pending[0].resolve(packet('a'));await flush();
 assert.equal(states.at(-1).snapshot.version_id,'b');assert.equal(timers.size,1);
 c.setVisible(false);assert.equal(timers.size,0);
 c.setVisible(true);assert.equal(pending.length,3);
 c.destroy();assert.equal(pending[2].signal.aborted,true);pending[2].resolve(packet('b'));await flush();assert.equal(timers.size,0);
});
test('refresh preserves old image until a verified image arrives, coalesces requests, and backs off',async()=>{
 let fail=false,calls=0,decode;
 const {c,states,timers}=fixture(async r=>{calls++;if(fail)throw new Error('network');return packet(r.id);},()=>new Promise(resolve=>{decode=resolve;}));
 c.select(a);await flush();assert.equal(states.at(-1).snapshot,null);c.refresh();assert.equal(calls,1);
 decode({width:1200,height:720});await flush();assert.equal(states.at(-1).phase,'ready');
 fail=true;await c.refresh();assert.equal(states.at(-1).phase,'error');assert.equal(states.at(-1).snapshot.version_id,'a');assert.ok([...timers.values()].some(t=>t.ms===120000));c.destroy();
});
test('authentication pauses automatic retries; manual refresh can recover',async()=>{
 let fail=true;const {c,states,timers}=fixture(async r=>{if(fail)throw Object.assign(new Error('auth'),{code:'AUTH_REQUIRED'});return packet(r.id);});
 c.select(a);await flush();assert.equal(states.at(-1).phase,'blocked');assert.equal(timers.size,0);
 c.setVisible(false);c.setVisible(true);assert.equal(timers.size,0);
 fail=false;await c.refresh();assert.equal(states.at(-1).phase,'ready');assert.equal(timers.size,1);c.destroy();
});
test('cached image displays before remote refresh; malformed/mismatched responses cannot replace it',async()=>{
 const {c,states}=fixture(async()=>packet('wrong'));
 c.select({...a,preview:packet('a')});await flush();assert.equal(states.at(-1).phase,'error');assert.equal(states.at(-1).snapshot.version_id,'a');c.destroy();
});
test('transport passes project/version and signal, maps permissions without browser credentials',async()=>{
 const seen=[];const signal=new AbortController().signal;
 const transport=previewTransport({meta:{case_finding_preview:true}},'p',async(url,options)=>{seen.push({url,options});return {ok:false,status:403};});
 await assert.rejects(transport(a,signal),{code:'FORBIDDEN'});assert.equal(seen[0].url,'/api/case-finding/preview?project=p&version=a');assert.equal(seen[0].options.signal,signal);
});

test('board jump follows selected version, keeps anchors, opens a new tab and disables missing targets',()=>{
 const link={attrs:{},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this[k]}};
 const v1='https://team.feishu.cn/docx/DocOne#board-one';
 const v2='https://team.feishu.cn/docx/DocTwo#board-two';
 assert.equal(setBoardLink(link,{board_url:v1,document_url:'https://team.feishu.cn/docx/DocOne'}),v1);
 assert.equal(link.href,v1);assert.equal(link.target,'_blank');assert.equal(link.rel,'noopener noreferrer');assert.equal(link.attrs['aria-disabled'],'false');
 setBoardLink(link,{board_url:v2});assert.equal(link.href,v2);
 setBoardLink(link,{document_url:v1});assert.equal(link.href,v1);
 setBoardLink(link,null);assert.equal(link.href,undefined);assert.equal(link.attrs['aria-disabled'],'true');
 for(const value of ['javascript:alert(1)','https://feishu.cn.evil.test/docx/x','https://user:pass@team.feishu.cn/docx/x','http://team.feishu.cn/docx/x'])assert.equal(originalUrl(value),null);
});

test('reserved research waits for board binding without polling Feishu',async()=>{
 let calls=0;const transport=previewTransport({meta:{case_finding_preview:true}},'p',()=>{calls++;});
 const {c,states,timers}=fixture(transport);c.select({...a,board_token:null});await flush();
 assert.equal(calls,0);assert.equal(states.at(-1).phase,'unbound');assert.equal(timers.size,0);c.destroy();
});
