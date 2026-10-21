# Yu+ 官网

纯静态站点，GitHub Actions 仅将本目录发布到 GitHub Pages。不依赖本地应用服务，不公开业务数据。

本地预览：`python3 -m http.server 8080 --directory website`。

`install-prompt.txt` 是简短的启动提示词，`index.html` 的只读 textarea 保留相同内容供复制和无 JavaScript 阅读。完整安装流程放在 `agent-install.md`，短提示词指向官网上的这份 Markdown。修改短提示词时同步两处；更新流程只需维护 Markdown。指南固定到 v0.2.2 Release；只有发布新版本后才更换下载地址及摘要。

按钮复制短提示词；Clipboard API 不可用时展开并选中文字，不谎报复制成功。所有样式、脚本和图标由本站提供，无第三方字体、追踪或运行时依赖。
