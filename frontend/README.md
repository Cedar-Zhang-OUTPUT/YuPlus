# Yu+ 前端预览

根据用户提供的 `yuplus-handoff.zip` 设计和源码落地的可交互页面。沿用交付包的浅色材质、字号、四类主题色、圆角卡片和按需检查器；不是之前的两种视觉概念图。

## 启动

Node.js ≥ 20.11，无第三方依赖，无需 npm install。在仓库根目录：

```sh
npm --prefix frontend run dev
# http://127.0.0.1:7801

# 指定其他端口
npm --prefix frontend run dev -- --port 7802

npm --prefix frontend test
```

浏览器刷新后读取更新后的源码/数据；服务代码修改需要重启进程。服务仅绑定本机，提供 `public/` 中的静态文件，不读取真实项目数据库、凭证或本地材料目录。除下述 Finder 定位操作外，拒绝写入方法。

## 可调试的页面

- 项目列表：`/#/`，包含同名项目、空项目和归档项目。
- 交付细节：`/#/p/prj_city/draft/obj_deliv`。
- 预算与采用决定：`/#/p/prj_city/draft/obj_budget`。
- 创作者 Brief：`/#/p/prj_city/review/obj_r04`；另有视觉设计师实例。
- Debrief 与历史版本：`/#/p/prj_city/review/obj_r01`。
- Q&A：`/#/p/prj_city/review/obj_qa`，读取同一个 D15 对象。
- 材料：`/#/p/prj_city/sources`；变更与决定：`/#/p/prj_city/history`。
- 23 类对象说明：`/#/types`。

城市记忆展厅有 23 类带内容的 draft、23 类对象目录、4 类持久化 review 的 5 份成果以及共用 D15 的 R05 视图。页面支持来源快照/原文分流、反向引用、历史版本、完整段落追溯、复制引用和项目内导航。浏览不会改变项目工作场景。

## 文件职责

- `public/styles/tokens.css`：交付包提供的设计 token。
- `public/styles/app.css`：页面/组件样式与自适应规则。
- `public/app.js`：只读视图、交互及 hash 路由。
- `public/data/demo.js`：稳定的模拟视图数据，可修改后刷新页面调试。
- `public/data/selectors.js`：条目级依据比较。以后接入服务时，以 `review.prepare` 的权威受影响信息替代。
- `public/source.html`、`source.js`：模拟原文的新标签页。
- `server.mjs`：独立前端预览服务，不是 `yu serve`，不改变 Python CLI。
- `tests/preview.test.mjs`：引用完整性、依据变化与只读服务边界测试。

## 与交付包的调整

修复了搜索丢焦、历史 draft 不能切换、R05 路由未读取共用对象、跨项目对象地址可能展示其他项目内容、空项目“全部 23 类”目录不全、窄窗口缺少导航和搜索框溢出等问题。依据比较落到具体条目，避免同一对象中的无关条目一起提示变更。

按既有 spec 的能力边界，不预置未实现的远端扫描、审核确认或飞书导出状态。飞书标题仍是新标签页链接，但本轮指向本地示例原文，避免访问交付包内虚构的域名。接真实来源时需恢复真实规范地址。

素材列表保留交付包提供的文件信息和预览占位；交付包没有这些业务图片/PDF/音视频的真实文件。当前不承诺实际多媒体预览或实时同步。这是前端视图模型，不是可直接提交给 CLI 的 JSON 契约，也不代表所有示例字段已在后端实现。

设计参考保存在 `../docs/design/handoff/`，本轮浏览器截图在 `../docs/design/qa-2026-10-16/`。检查记录见 `design-qa.md`。

## 在 Finder 中显示

macOS 本地预览支持从附件卡片点击“在 Finder 中显示”。服务将已有 Markdown / 文本正文保存到 `frontend/.preview/source-files/`（Git 忽略），并用系统 `open -R` 选中文件。这是本地模拟快照，不是飞书原件。没有真实内容的图片、PDF 等占位附件不会显示按钮；非 macOS 环境也不会显示。

`GET /api/local-files` 只返回可用附件标识；`POST /api/local-files/reveal` 仅接受同源 JSON 请求中的 `versionId` / `assetId`。路径由服务内部登记，客户端不能指定任意路径或命令，缓存文件也不通过静态服务器提供。此桥接只服务当前本机预览，未接入实际项目材料库。

## Review 的 Agent Prompt

标题右侧“复制飞书导出 Prompt”汇总当前项目所有 Review 实例及共用的客户 Q&A，附带引用过的 draft 历史版本、当前版本、原始来源快照和段落依据状态。变化提示内“复制更新 Prompt”仅针对当前成果检查更新。两者均由 `public/data/review-prompts.js` 根据点击时的数据生成，页面只写入剪贴板，不执行业务更新或外部导出。

当前 Prompt 明确标记模拟数据：更新指向仓库内的示例版本；飞书导出由用户将 Prompt 发送给 Agent 后，通过已安装的飞书 CLI 创建并核验新文档。来源正文作为阅读材料传递，不当作命令执行。未来接入真实数据时，需由数据适配层提供真实项目上下文，并以 CLI 的 `review.prepare` / `review.publish` 契约完成更新；不能把当前视图 JSON 直接作为 CLI 输入。

## 最终设计与集成交接

用户已确认本阶段可视化设计完成；后续真实数据、CLI、服务和界面使用 skill 的集成要求见[交接说明](../docs/design/2026-10-16-frontend-integration-handoff.md)。该文包含后续迭代的最终交互约定，早期设计 QA 截图不覆盖全部变更。
