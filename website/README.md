# Yu+ 官网

纯静态站点，GitHub Actions 仅将本目录发布到 GitHub Pages。不依赖本地应用服务，不公开业务数据。

本地预览：`python3 -m http.server 8080 --directory website`。

`install-prompt.txt` 是下载版完整提示词，`index.html` 的只读 textarea 保留同一份内容供复制和无 JavaScript 阅读。修改提示词时同步两处。安装目标固定到 v0.1 Release；只有发布新版本后才更换地址。

按钮复制完整提示词；Clipboard API 不可用时展开并选中文字，不谎报复制成功。所有样式、脚本和图标由本站提供，无第三方字体、追踪或运行时依赖。
