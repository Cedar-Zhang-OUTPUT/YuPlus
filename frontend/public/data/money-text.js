// Match explicit monetary amounts without treating dates, counts or percentages as money.
export function moneyMatches(text) {
  const number = String.raw`[+-]?\d[\d,]*(?:\.\d+)?`;
  const amount = `${number}(?:\\s*[–—~～至到-]\\s*${number})?`;
  const currency = String.raw`(?:人民币|美元|港元|港币|欧元|英镑|日元|元|CNY\b|RMB\b|USD\b|HKD\b|EUR\b|GBP\b|JPY\b)`;
  const explicit = new RegExp(`(?:[¥￥$€£]\\s*${amount}(?:\\s*[万亿])?|${currency}\\s*${amount}(?:\\s*[万亿])?|${amount}\\s*(?:[万亿]\\s*)?${currency})`, 'gi');
  const matches = [...text.matchAll(explicit)].map(m => ({ index:m.index, text:m[0] }));
  // Chinese budget prose often omits “元”, e.g. “客户 100 万，按 60 万执行”.
  if (/预算|金额|费用|报价|采购|执行|客户|付款|支付|成本|投入|口径/.test(text)) {
    for (const m of text.matchAll(new RegExp(`${amount}\\s*[万亿](?!\\s*(?:元|人|字|次|个|件|年|条|支|台|份|平方米))`, 'g'))) {
      if (!matches.some(x => m.index < x.index + x.text.length && m.index + m[0].length > x.index))
        matches.push({ index:m.index, text:m[0] });
    }
  }
  return matches.sort((a,b) => a.index-b.index);
}

// CLI amounts are integer strings; never lose cents through Number coercion.
export function formatMinor(minor, currency) {
  if (minor === null || minor === undefined || !/^-?\d+$/.test(String(minor))) return null;
  const amount=BigInt(minor), absolute=amount<0n ? -amount : amount;
  const fraction=String(absolute%100n).padStart(2,'0').replace(/0+$/,'');
  return `${amount<0n?'-':''}${(absolute/100n).toLocaleString('zh-CN')}${fraction?'.'+fraction:''} ${currency==='CNY'?'元':currency||''}`.trim();
}
