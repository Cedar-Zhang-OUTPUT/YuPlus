import test from 'node:test';
import assert from 'node:assert/strict';
import { moneyMatches } from '../public/data/money-text.js';

test('monetary values include currencies, ranges and contextual budget shorthand', () => {
  const values = text => moneyMatches(text).map(m => m.text);
  assert.deepEqual(values('金额 1,000,000 元，报价 5–10 万元，USD 2,500，￥800'), ['1,000,000 元','5–10 万元','USD 2,500','￥800']);
  assert.deepEqual(values('客户 100 万含设备，我们执行按 60 万推进'), ['100 万','60 万']);
  assert.deepEqual(values('2026-10-16 14:30，8 分钟，3 面，40%，受众 100 万人'), []);
  assert.deepEqual(values('客户希望吸引 100 万人，预算 60 万元'), ['60 万元']);
});

test('integer minor units retain cents beyond JavaScript safe integers',async()=>{
  const {formatMinor}=await import('../public/data/money-text.js');
  assert.equal(formatMinor('9007199254740993','CNY'),'90,071,992,547,409.93 元');
  assert.equal(formatMinor('60000000','CNY'),'600,000 元');
  assert.equal(formatMinor('-1','USD'),'-0.01 USD');
  assert.equal(formatMinor(null,'CNY'),null);
  assert.equal(formatMinor('','CNY'),null);
});
