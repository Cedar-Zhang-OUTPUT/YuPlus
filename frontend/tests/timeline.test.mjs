import test from 'node:test';
import assert from 'node:assert/strict';
import { parseScheduleTime, milestoneDates, timelineScale } from '../public/data/timeline.js';

test('dates retain day precision and datetime values retain minute precision', () => {
  assert.equal(parseScheduleTime('2027-01-05').label, '2027-01-05');
  assert.equal(parseScheduleTime('2027-01-05').hasTime, false);
  assert.equal(parseScheduleTime('2027-01-05T09:35').label, '2027-01-05 09:35');
  assert.equal(parseScheduleTime('2027-01-05 09:35:42').label, '2027-01-05 09:35');
  assert.equal(parseScheduleTime('2027-01-05T00:00').hasTime, true);
});

test('invalid calendar dates and out-of-range times are rejected', () => {
  for (const value of ['2027-02-29', '2027-02-30', '2027-13-01', '2027-01-05T24:00', '2027-01-05T09:60', '2027-01-05T09:30:60', 'tomorrow', '']) {
    assert.equal(parseScheduleTime(value), null, value);
  }
  assert.ok(parseScheduleTime('2028-02-29'));
});

test('zoned timestamps display in local time without changing date-only values', () => {
  const value = '2027-01-05T09:35:00+08:00';
  const local = new Date(value);
  const parsed = parseScheduleTime(value);
  assert.equal(parsed.value, Date.UTC(local.getFullYear(), local.getMonth(), local.getDate(), local.getHours(), local.getMinutes()));
  assert.equal(parseScheduleTime('2027-01-05').label, '2027-01-05');
});

test('minute intervals, day intervals and points coexist and sort chronologically', () => {
  const point = milestoneDates({data:{date:'2027-01-05T09:35'}});
  const range = milestoneDates({data:{start:'2027-01-05T10:15',end:'2027-01-05T11:45'}});
  const days = milestoneDates({data:{start:'2027-01-05',end:'2027-01-18'}});
  assert.equal(point.from, point.to);
  assert.equal(range.to-range.from, 90*60000);
  assert.equal(days.to-days.from, 13*86400000);
  assert.deepEqual([point,range,days].sort((a,b)=>a.from-b.from),[days,point,range]);
  const scale = timelineScale([point,range,days]);
  assert.ok(scale.min < days.from && scale.max > days.to);
  assert.equal(scale.last, '2027-01-18');
});

test('short schedules use timed ticks and preserve the exact final minute', () => {
  const range = milestoneDates({data:{start:'2027-01-05T10:15',end:'2027-01-05T11:45'}});
  const scale = timelineScale([range]);
  assert.equal(scale.minuteScale, true);
  assert.equal(scale.last, '2027-01-05 11:45');
  assert.ok(scale.ticks.every(t=>t.label.includes(':')));
  const single = timelineScale([milestoneDates({data:{date:'2027-01-05T10:15'}})]);
  assert.ok(single.max>single.min && single.ticks.length>0);
});
