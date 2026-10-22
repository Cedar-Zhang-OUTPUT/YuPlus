const blank = '______';
const value = text => String(text ?? '').trim() || blank;

export function projectCreationPrompt(kind, fields = {}) {
  const base = `用 Yu+ 新建一个项目，名称：${value(fields.name)}；客户/简述：${value(fields.summary)}。建立后把 project_id 告诉我。`;
  return base + (kind === 'monitor'
    ? `顺便去监控这个飞书群的消息：${value(fields.chat)}`
    : '这是一些文件给到你：');
}

// Only prepares clipboard text. Project creation and monitoring remain Agent actions.
export function createProjectPromptTemplate(kind, values, copy) {
  const make = (tag, className, text) => {
    const node = document.createElement(tag);
    node.className = className;
    if (text) node.textContent = text;
    return node;
  };
  const title = kind === 'monitor' ? '新建项目并监控飞书群' : '新建项目并提供文件';
  const row = make('section', 'project-prompt-template');
  row.setAttribute('aria-label', title);
  row.append(make('h4', 'project-prompt-title', title));
  const box = make('div', 'copyable project-prompt-box');
  const text = make('div', 'project-prompt-text');
  const inputs = {};
  const appendText = content => text.append(make('span', '', content));
  const appendInput = (key, label) => {
    const input = make('input', `project-prompt-input project-prompt-${key}`);
    input.type = 'text';
    input.placeholder = blank;
    input.value = values[key] || '';
    input.setAttribute('aria-label', `${title}：${label}`);
    input.autocomplete = 'off';
    input.oninput = () => { values[key] = input.value; };
    inputs[key] = input;
    text.append(input);
  };
  appendText('用 Yu+ 新建一个项目，名称：');
  appendInput('name', '项目名称');
  appendText('；客户/简述：');
  appendInput('summary', '客户或项目简述');
  appendText('。建立后把 project_id 告诉我。');
  if (kind === 'monitor') {
    appendText('顺便去监控这个飞书群的消息：');
    appendInput('chat', '飞书群链接或群 ID');
  } else {
    appendText('这是一些文件给到你：');
  }
  const button = make('button', 'chipbtn', '复制');
  button.type = 'button';
  button.setAttribute('aria-label', `复制${title}提示词`);
  button.onclick = () => {
    for (const [key, input] of Object.entries(inputs)) values[key] = input.value;
    copy(projectCreationPrompt(kind, values), button);
  };
  box.append(text, button);
  row.append(box);
  return row;
}
