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
