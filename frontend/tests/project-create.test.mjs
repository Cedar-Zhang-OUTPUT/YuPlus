import test from 'node:test';
import assert from 'node:assert/strict';
import {projectCreationPrompt,createProjectPromptTemplate} from '../public/data/project-create.js';

const base='用 Yu+ 新建一个项目，名称：______。建立后把 project_id 告诉我。';
test('both unfilled templates copy the requested wording with underscore slots',()=>{
  assert.equal(projectCreationPrompt('materials'),base+'这是一些文件给到你：');
  assert.equal(projectCreationPrompt('monitor'),base+'顺便去监控这个飞书群的消息：______');
});
test('filled and partially filled templates retain user content and normalize blank slots',()=>{
  const text=projectCreationPrompt('monitor',{name:'  城市展  ',chat:'https://feishu.cn/chat?x=1&y=2'});
  assert.equal(text,'用 Yu+ 新建一个项目，名称：城市展。建立后把 project_id 告诉我。顺便去监控这个飞书群的消息：https://feishu.cn/chat?x=1&y=2');
  assert.ok(projectCreationPrompt('materials',{name:'<艺术> & 项目',summary:'不应出现'}).includes('名称：<艺术> & 项目。'));
  assert.ok(!projectCreationPrompt('materials',{summary:'不应出现'}).includes('不应出现'));
});
test('inline fields feed each copy action without submitting project writes',()=>{
  const previous=globalThis.document;
  globalThis.document={createElement:tag=>({tag,children:[],attrs:{},append(...nodes){this.children.push(...nodes)},setAttribute(k,v){this.attrs[k]=v}})};
  const nodes=root=>[root,...root.children.flatMap(nodes)];
  try {
    const copies=[];const values={};
    const template=createProjectPromptTemplate('monitor',values,(text)=>copies.push(text));
    const elements=nodes(template);const inputs=elements.filter(n=>n.tag==='input');
    assert.equal(inputs.length,2);
    assert.deepEqual(inputs.map(n=>n.placeholder),['项目名','飞书群聊名称']);
    assert.ok(inputs.every(n=>n.attrs['aria-label']));
    const copy=elements.find(n=>n.tag==='button');assert.equal(copy.type,'button');
    inputs[0].value='测试项目';inputs[0].oninput();
    inputs[1].value='策展沟通群';
    assert.deepEqual(copies,[]);
    copy.onclick();
    assert.equal(copies[0],projectCreationPrompt('monitor',{name:'测试项目',chat:'策展沟通群'}));
    inputs.forEach(n=>{n.value='  ';});copy.onclick();
    assert.equal(copies[1],base+'顺便去监控这个飞书群的消息：______');
    assert.equal(nodes(createProjectPromptTemplate('materials',{},()=>{})).filter(n=>n.tag==='input').length,1);
  } finally {globalThis.document=previous;}
});
