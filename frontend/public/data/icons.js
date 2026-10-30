// 统一的线性图标：24×24、1.7px 描边、圆角端点，颜色继承 currentColor。
// 仅用于界面装饰（aria-hidden），不承载信息；文字标签始终保留。
const PATHS = {
  grid: 'M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z',
  library: 'M4 4.5h4v15H4z M10 4.5h4v15h-4z M15.6 5.2l3.9 1-3.2 13.7-3.9-1z',
  layers: 'M12 3.5 3 8.2l9 4.8 9-4.8-9-4.7z M3 12.4l9 4.8 9-4.8 M3 16.6l9 4.8 9-4.8',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5.2l3.3 2',
  doc: 'M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z M14 3v5h5 M8.5 12.5h7 M8.5 16h5',
  folder: 'M3 7.5A2 2 0 0 1 5 5.5h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  mic: 'M12 3a3 3 0 0 0-3 3v5.5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z M5.5 11a6.5 6.5 0 0 0 13 0 M12 17.5V21',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M3 12h18 M12 3c2.4 2.5 3.7 5.5 3.7 9s-1.3 6.5-3.7 9c-2.4-2.5-3.7-5.5-3.7-9S9.6 5.5 12 3z',
  plus: 'M12 5v14 M5 12h14',
  minus: 'M5 12h14',
  slash: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M5.6 18.4 18.4 5.6',
  x: 'M6 6l12 12 M18 6 6 18',
  menu: 'M4 7h16 M4 12h16 M4 17h16',
  refresh: 'M20 6v5h-5 M20 11a8 8 0 1 0-2.3 5.7',
  edit: 'M4 20h4L19 9l-4-4L4 16z M13.5 6.5l4 4',
  help: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M9.6 9.3a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.8 M12 17.2h.01',
  flag: 'M5 21V4 M5 4h11l-2 4 2 4H5',
  dashed: 'M12 3a9 9 0 0 1 3.4.7 M19.2 6.6A9 9 0 0 1 21 12 M19.4 17.3A9 9 0 0 1 15.4 20.3 M12 21a9 9 0 0 1-3.4-.7 M4.8 17.4A9 9 0 0 1 3 12 M4.6 6.7A9 9 0 0 1 8.6 3.7',
  image: 'M4 5h16v14H4z M4 16l4.5-4.5 4 4 2.5-2.5L20 18 M15.5 9.5h.01',
  film: 'M4 5h16v14H4z M8 5v14 M16 5v14 M4 9.5h4 M4 14.5h4 M16 9.5h4 M16 14.5h4',
};

// 旧的字符/emoji 图标 → 新图标名，保证调用方无需改动即可统一风格
const GLYPHS = { '📁': 'folder', '🗂': 'layers', '📄': 'doc', '✎': 'edit', '?': 'help', '◆': 'flag', '◷': 'clock',
  '○': 'dashed', '↻': 'refresh', '🎙': 'mic', '🔗': 'globe', '🖼': 'image', '🎬': 'film', '＋': 'plus', '∅': 'slash' };

export function iconName(glyph) { return PATHS[glyph] ? glyph : GLYPHS[glyph] || null; }

export function icon(name, size = 18) {
  const key = iconName(name);
  if (!key) return null;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', String(size)); svg.setAttribute('height', String(size));
  svg.setAttribute('aria-hidden', 'true'); svg.setAttribute('focusable', 'false');
  svg.setAttribute('class', 'ui-icon');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', PATHS[key]);
  path.setAttribute('fill', 'none'); path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '1.7'); path.setAttribute('stroke-linecap', 'round'); path.setAttribute('stroke-linejoin', 'round');
  svg.append(path);
  return svg;
}
