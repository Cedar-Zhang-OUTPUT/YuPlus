'use strict';
(() => {
  const prompt = document.querySelector('#install-prompt');
  const status = document.querySelector('#copy-status');
  let statusTimer;
  function notify(message) {
    clearTimeout(statusTimer);
    status.textContent = message;
    status.classList.add('visible');
    statusTimer = setTimeout(() => status.classList.remove('visible'), 6500);
  }
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      const text = prompt.value;
      try {
        if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
        await navigator.clipboard.writeText(text);
        notify('已复制短提示词，粘贴到 Codex 后由 Agent 阅读安装指南。');
      } catch {
        document.querySelector('#full-prompt').open = true;
        prompt.focus();
        prompt.select();
        prompt.setSelectionRange(0, text.length);
        notify('浏览器未允许复制，已选中短提示词，请手动复制。');
      }
    });
  });
})();
