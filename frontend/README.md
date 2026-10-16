# Yu+ 只读前端

沿用用户交付并确认的页面设计。正式模式由 Python 网关提供真实数据；独立 Node 服务保留为模拟设计预览。两者使用同一套页面，不需要前端构建或 npm 依赖。

## 正式运行

在仓库根目录安装 Python 包后：

```sh
.venv/bin/yu --data-dir .local/work start --json
```

打开启动 JSON 中的实际 URL；status 可恢复地址，stop 只停止核验过的托管服务。serve --port 0 仍可前台运行。`/api/health` 返回 `mode: live`、URL、端口和绝对数据目录。端口 0 自动分配；不要假设 7801 是正式服务。wheel 包含生产页面资源，安装后无需源码或 Node。

`GET /api/view` 返回项目目录；`GET /api/view?project=PROJECT_ID` 返回指定项目的对象、全部已保存版本、来源、变更与决定，以及后端计算的条目级依据状态。API 出错显示读取失败，不渲染为空项目或模拟项目。CLI 保存后点击“刷新页面”或浏览器重载查看；同一项目内导航可复用已加载快照。

## 路由

- 项目列表：`/#/`；对象说明：`/#/types`。
- 信息收集：`/#/p/PROJECT_ID/draft/OBJECT_ID`。
- 整理与 Review：`/#/p/PROJECT_ID/review/OBJECT_ID`；R05 的 OBJECT_ID 就是 D15 对象。
- 材料：`/#/p/PROJECT_ID/sources`；历史：`/#/p/PROJECT_ID/history`。
- 对象 ID 可省略以进入对应场景。浏览不会切换 Agent 的项目或持久化工作场景。

## 真实内容、来源与文件

23 类对象使用正式目录与契约字段。金额整数保留最小单位精度；时间保留日/分钟精度。Review 按实际实例显示，多个创作者 Brief 不合并。完整正文使用安全的文本 Markdown 子集（标题、段落、粗体、代码、列表、引用、基础表格、HTTP(S) 链接），不执行材料 HTML。

“查看引用”打开实际引用的本地快照，包含标题、采集范围、版本、正文与附件；原文标题打开保存的真实远端 URL，不再替换为模拟原文。历史引用不被来源头版本覆盖。缺少依据显示无法核对，不当作已同步。

登记的真实资产通过 `/api/assets?project=...&version=...&asset=...` 读取；返回前核验大小和哈希。支持常见图片预览及浏览器支持的音视频播放，提供“打开文件”查看原件；PDF 可在新标签页交给浏览器查看。其他格式由浏览器下载/打开；HTML、SVG 等主动内容强制附件下载。没有独立“下载”按钮，保存方式取决于浏览器。缺失/变化文件如实提示。

macOS 上“在 Finder 中显示”只定位当前项目登记且核验通过的文件。`GET /api/local-files?project=...` 返回能力和资产 ID；同源 `POST /api/local-files/reveal` 仅接受 `projectId/versionId/assetId`，不接受任意路径或 shell 命令。它不修改业务数据。非 macOS 不提供 Finder 操作。

## Review 更新、导出与追溯

保持既有目录、版本切换、依据对比和追溯检查器的交互。依据变化由后端实际条目/间接依赖判断，无关条目变化不让整份成果失效。差异使用真实旧/新版本，不推测被删除条目的替代关系。

“复制引用”“复制更新 Prompt”“复制飞书导出 Prompt”只写剪贴板。正式 Prompt 绑定真实项目、数据目录和版本，不携带整库正文、不要求改 demo。Agent 重新读取当前内容，先改 draft，再 prepare/publish，最后刷新页面。

完整导出面向所有当前 Review 实例与共用 Q&A。`python -m yuplus.export_bundle` 只准备本地 Markdown/manifest；Agent 按飞书 Skill 创建并回读新文档后返回真实链接。应用没有导出历史或审核确认写入命令，不模拟成功记录；附件元信息不等于上传了附件。

## 独立模拟预览

```sh
# Node.js ≥20.11，无需安装 npm 依赖
npm --prefix frontend run dev
# 默认 http://127.0.0.1:7801；可加 -- --port 7802
npm --prefix frontend test
```

此服务的 health mode 是 `demo`，只在这个明确模式下加载 `data/demo.js`。示例项目 ID（如 prj_city）、本地原文页面和 Finder 缓存不是真实材料；不得用于生产写入。正式错误不会回退到 demo。

## 代码与边界

- `public/styles/`：保留交付包布局和视觉样式。
- `public/app.js`：只读视图、交互、hash 路由；`data/runtime.js` 加载真实视图，`vocabulary.js` 提供静态显示词汇。
- `data/selectors.js`：正式模式使用服务端依据状态；`basis-diff.js` 展示旧/新具体内容。
- `data/review-prompts.js`：复制时生成上下文与指引。
- `src/yuplus/browser_view.py`、`gateway.py`：只读 SQLite 快照、项目隔离、文件访问与本机 HTTP 服务。
- `server.mjs`、`data/demo.js`、`source.html/source.js`：独立模拟预览。

当前选定项目的视图一次读取全部已保存版本，资产逐个做完整哈希校验；大量历史或大视频可能影响加载速度，尚未做分页或校验缓存。新服务启动会后台检查飞书来源；页面刷新后显示检查结果。没有实时推送或编辑/审批/聊天界面。本轮沿用[交接说明](../docs/design/2026-10-16-frontend-integration-handoff.md)，验证范围见[集成验收](../docs/validation/2026-10-16-live-integration.md)。
