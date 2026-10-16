// Calendar coordinates keep date-only entries as dates. Zoned timestamps are
// displayed in the browser's local timezone before placing them on the same axis.
const DAY = 86400000;
const pad = (value) => String(value).padStart(2, "0");
export function parseScheduleTime(input) {
  if (typeof input !== "string") return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d{1,3})?)?(Z|[+-]\d{2}:\d{2})?)?$/.exec(input);
  if (!match) return null;
  const [, y, mo, d, h, mi, sec, zone] = match;
  const year = +y, month = +mo, day = +d, hour = +(h || 0), minute = +(mi || 0);
  let value = Date.UTC(year, month - 1, day, hour, minute);
  const check = new Date(value);
  if (year < 100 || check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day || hour > 23 || minute > 59 || +(sec || 0) > 59) return null;
  if (zone) {
    const instant = new Date(input.replace(" ", "T"));
    if (!Number.isFinite(instant.getTime())) return null;
    value = Date.UTC(instant.getFullYear(), instant.getMonth(), instant.getDate(), instant.getHours(), instant.getMinutes());
  }
  const calendar = new Date(value);
  const date = `${calendar.getUTCFullYear()}-${pad(calendar.getUTCMonth()+1)}-${pad(calendar.getUTCDate())}`;
  const hasTime = h !== undefined;
  return { value, hasTime, label: date + (hasTime ? ` ${pad(calendar.getUTCHours())}:${pad(calendar.getUTCMinutes())}` : "") };
}
export function milestoneDates(item) {
  const d = item.data;
  const rawStart = d.date || d.start;
  const rawEnd = d.date || d.end || rawStart;
  const start = parseScheduleTime(rawStart), end = parseScheduleTime(rawEnd);
  return { start: start?.label || rawStart, end: end?.label || rawEnd,
    from: start?.value ?? NaN, to: end?.value ?? NaN,
    hasTime: !!(start?.hasTime || end?.hasTime) };
}
export function timelineScale(dates) {
  const first = dates.reduce((a,b) => a.from <= b.from ? a : b);
  const last = dates.reduce((a,b) => a.to >= b.to ? a : b);
  const span = last.to - first.from;
  const minuteScale = dates.some((d) => d.hasTime) && span <= 2 * DAY;
  const padding = Math.max(span * .06, minuteScale ? 30 * 60000 : DAY / 2);
  const min = first.from - padding, max = last.to + padding;
  const ticks = [];
  if (span > 45 * DAY) {
    let at = new Date(min);
    at = Date.UTC(at.getUTCFullYear(), at.getUTCMonth(), 1);
    if (at < min) {
      const d = new Date(at);
      ticks.push({ value:min, label:`${d.getUTCMonth()+1}月`, title:`${d.getUTCFullYear()}年${d.getUTCMonth()+1}月` });
      at = Date.UTC(d.getUTCFullYear(), d.getUTCMonth()+1, 1);
    }
    while (at <= max && ticks.length < 100) {
      const d = new Date(at);
      ticks.push({ value: at, label: `${d.getUTCMonth()+1}月`, title: `${d.getUTCFullYear()}年${d.getUTCMonth()+1}月` });
      at = Date.UTC(d.getUTCFullYear(), d.getUTCMonth()+1, 1);
    }
  } else {
    const target = (max-min) / 5;
    const step = minuteScale
      ? ([15,30,60,180,360,720,1440].map((n) => n*60000).find((n) => n >= target) || DAY)
      : Math.max(1, Math.ceil(target / DAY)) * DAY;
    for (let at = Math.ceil(min / step) * step; at <= max; at += step) {
      const d = new Date(at);
      const date = `${pad(d.getUTCMonth()+1)}/${pad(d.getUTCDate())}`;
      const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
      const crossDay = Math.floor(min / DAY) !== Math.floor(max / DAY);
      ticks.push({ value:at, label: minuteScale ? (crossDay ? `${date}\n${time}` : time) : date, title: minuteScale ? `${date} ${time}` : date });
    }
  }
  return { min, max, ticks, first:first.start, last:last.end, minuteScale };
}
