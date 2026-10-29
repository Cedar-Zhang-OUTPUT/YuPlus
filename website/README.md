# Yu+ 官网

纯静态站点，GitHub Actions 仅将本目录发布到 GitHub Pages。不依赖本地应用服务，不公开业务数据。

首屏是可交互的产品演示（`demo.js`）：模拟 Codex 窗口与内置浏览器中的 Yu+ 只读页面。访客选择或输入一句话发送后，按预设动画展示资料整理、策划文档生成、修改追溯与案例分析画板（命令细节按需展开）；内容来自 Yu+ 前端自带的示例项目「城市记忆展厅」，不连接飞书或任何服务。面板宽度可拖动，画板可平移缩放，`prefers-reduced-motion` 下动画即时完成。修改 Yu+ 页面视觉时，同步 `site.css` 中「Yu+ 页面」一节。

本地预览：`python3 -m http.server 8080 --directory website`。

`install-prompt.txt` 是简短的启动提示词，`index.html` 的只读 textarea 保留相同内容供复制和无 JavaScript 阅读。完整安装流程放在 `agent-install.md`，短提示词指向官网上的这份 Markdown。修改短提示词时同步两处；更新流程只需维护 Markdown。指南固定到 v0.3.25 Release；只有发布新版本后才更换下载地址及摘要。

按钮复制短提示词；Clipboard API 不可用时展开并选中文字，不谎报复制成功。所有样式、脚本和图标由本站提供，无第三方字体、追踪或运行时依赖。
