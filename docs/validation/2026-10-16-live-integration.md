# 2026-10-16 真实数据与服务集成验收

依据 [前端交接说明](../design/2026-10-16-frontend-integration-handoff.md) 完成接入。沿用交付包的页面布局与样式，未修改 CSS；页面代码调整限于真实数据、来源与依赖、字段解释、内容呈现和操作绑定。

## 验收结果

| 范围 | 结果与证据 |
| --- | --- |
| 后端自动测试 | `python -m unittest discover -s tests -q`：107 项通过，包含网关、完整导出和可重复 CLI 链路验收。 |
| 前端自动测试 | `npm --prefix frontend test`：29 项通过；`node --check frontend/public/app.js` 通过。 |
| 契约 | `docs/superpowers/specs/contracts/v0.1/verify_contracts.py`：94 项检查通过。 |
| Skill | 业务与可视化两份主 Skill 均通过 skill-creator 的 quick_validate；英文参考和中文版本同步。仓库内文件已更新，不代表已安装到用户全局 Skill 目录。 |
| 安装包 | 最终 wheel 在仓库外 `/tmp` 通过隔离 target 安装目录启动网关；首页、runtime、provenance、CSS、health 和真实 view API 均为 200。确认静态 UI 随包分发，未包含 demo 数据文件。 |
| 独立审查 | 审查发现的 Q&A 状态映射、间接依赖差异与追溯、整对象标题及顺序变化均已修复；复核无剩余重要发现。 |

## 实际完整链路

在隔离数据目录中使用合成材料，经真实 CLI 创建两个项目，收录本地文本、图片及口述材料，建立 draft，生成五个 review 实例（含两个创作者 Brief）和共用 D15/R05 Q&A。通过真实 HTTP API 验证项目隔离与登记资产读取。

先尝试没有合法原因的直接 review 改写，确认被拒绝；再收录新材料、修改 draft 视频交付项，确认只有相关成果段落过期，同一对象未变化的展墙项不受影响。随后按 draft 变更更新两个受影响成果，回读当前版本为新内容，历史版本保持旧内容。完整导出包包含五个成果实例、共用 Q&A 和来源附录，无缺失引用或警告。

另建间接依赖样例：Review → 策略 draft → 预算 draft。预算由 100 万变为 60 万，策略版本未变；页面仍能识别上游变化，比较实际预算旧值与新值，并沿历史版本追溯到原来源。该样例故意保留过期状态供检查，不属于主验收项目的未完成更新。

Codex 内置浏览器实际检查了当前成果、历史版本、直接及间接差异、追溯路径、真实图片解码、来源原文与资产入口、Q&A 状态和飞书来源标题/链接。最终主策 Debrief 为 v2，视频交付为“概念脚本”，展墙交付保持不变。页面错误日志为空。

复现入口为 [scripts/live_acceptance.py](../../scripts/live_acceptance.py)：先 `seed --root <新的隔离目录>`，启动该目录的 `yu serve --port 0 --json`，再 `finish --root <同一目录> --url <实际服务地址>`。脚本不执行飞书写入；外部导出验证是本次单独完成的步骤。

## 飞书实际导出与回读

使用 lark-doc Skill 和飞书 CLI，将合成资料导出为 [Yu+ 集成验收 · 合成资料 · 2026-10-16](https://k1mai98sti.feishu.cn/docx/DqbRd1nkFoWIfuxi2v2ctD6TnTZ)，创建后重新读取，远端 revision 为 4。

- 五个成果实例、一个共用 Q&A、来源附录及 29 个原样内容块均与本地导出对应。
- 本地 Markdown SHA-256：`388343dbda6d2607951af69f5a5fcc8741c3f41ef289cae55094a9890e3f3eda`。
- 导出快照哈希：`78799b35ebf6ca78b2525b06a689937a8ebac50742649b464dff922e413038ac`。
- 将该飞书文档回读结果以真实 URL、标题、revision 及正文收录为本地来源，页面可查看。

本机执行回执保留于忽略目录 `.preview/live-20261016c/`：`state.json`、`export/`、`feishu-create.json`、`feishu-readback.json`、`feishu-verification.json`、`feishu-import.json`。这些运行数据和测试文档内容不随代码提交。

## 明确边界

- 本轮验证使用真实程序与存储、合成业务资料，不能代替真实项目长期使用或所有 Agent 行为的评估。
- 导出保留媒体的登记信息与来源关系，本轮未上传图片、视频等媒体附件到飞书；没有写入数据库“导出成功”记录。
- 尚未实现后台飞书 revision 扫描、review 确认记录及导出历史持久化。页面通过刷新读取服务，不是实时推送。
- 真实资产验证覆盖文本、PNG 和 HTTP Range 等接口行为，未逐一验证全部 PDF、音视频格式及播放环境；Finder 原生唤起未在本次浏览器验收中点击验证。
- 当前视图读取所选项目的完整历史；资产读取会校验完整性。尚未做大型项目、超大媒体压力测试，也未验证跨系统安装。
- 页面保持业务只读，写入经 CLI。复制引用和 Prompt 只复制文本，不会触发 Agent 或直接更新业务数据。
