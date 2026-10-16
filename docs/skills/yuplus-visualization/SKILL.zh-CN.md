---
name: yuplus-visualization
description: 打开并解释 Yu+ 项目浏览器，包括导航、已保存来源、版本、依据变化、更新与飞书导出 Prompt，以及本地服务故障。适用于 Yu+ 界面使用问题；业务修改由 Yu+ 项目 skill 负责。
---

# Yu+ 可视化界面使用

帮助用户阅读已保存的 Yu+ 项目并使用真实控件。浏览器是业务数据的只读视图，可以复制引用/Prompt 和定位已登记文件；项目内容通过 CLI 保存。切换页面不会替 Agent 选定业务项目，也不会更改项目保存的工作场景。

## 只读取当前任务需要的说明

- 打开项目或排查页面不可达：[服务与打开页面](references/service.zh-CN.md)。
- 解释页面、目录、卡片、版本或来源控件：[界面指南](references/interface.zh-CN.md)。
- 解释依据变化、接收修改引用或导出：[Review 操作](references/review-actions.zh-CN.md)。
- 操作失败或状态不明：[故障处理](references/troubleshooting.zh-CN.md)。

复用本轮对话已经读过的说明。项目数据过期时刷新数据，不反复加载全部 skill、全部参考文件或整个项目历史。简单按钮问题直接回答，不必读取全部项目内容。

## 绑定真实项目

发现当前服务地址并检查 `/api/health`：确认 `mode: "live"`、实际 `url`、`port` 和解析后的 `data_dir`，再验证该目录中的真实项目 ID。不要假定 7801 永远是正式服务：`npm --prefix frontend run dev` 是独立示例演示，不连接用户数据库。不能用示例数据解释真实服务读取失败。

使用可用的浏览器工具打开已验证地址和相应 hash 路由，保留其他标签页。通过中文可见文字或无障碍名称定位控件，不依赖截图坐标。没有浏览器控制工具时，提供经过验证的可点击地址和准确操作步骤，不声称已打开或检查页面。

## 区分阅读与写入

- “复制引用”“复制更新 Prompt”“复制飞书导出 Prompt”都只复制文字。“已复制”不等于保存、同步或导出成功。
- 来源有原文地址时，点击标题在新标签页打开保存的原文地址；“查看引用”打开 Yu+ 已保存快照，可能是历史版。本地主快照不证明远端最新。
- 收到“修改这一段”时，解析项目 ID、数据目录、对象/段落/条目 ID 和所看版本，再重新读取当前目标。写入使用已安装的 `yuplus` 业务 skill。若已读过其指导，只补读相关参考，不在两个 skill 之间递归全量加载。
- 新事实或措辞要求先记录为相应 draft 依据，再 `review prepare`、`review publish`。不得把浏览器视图 JSON 直接写入 SQLite，也不得把复制的上下文当作 CLI 输入。
- 全项目飞书导出先准备本地已保存内容，再通过可用的飞书文档 skill 新建、写入、回读文档；只报告已核验结果和真实链接。

纯 Yu+ 软件开发、skill 编写或无关问题，不套用业务助手的回合末项目页脚。真正执行业务项目工作时，遵守业务 skill 的结果汇报要求。

## 维护依据

对应 2026-10-16 前端集成。行为代码：`frontend/public/app.js`、`data/runtime.js`、`data/review-prompts.js`、`data/basis-diff.js`；服务代码：`src/yuplus/gateway.py`、`browser_view.py`、`export_bundle.py`。这是仓库内的实现位置，不要求独立安装的 skill 目录包含这些文件。版本不同时，以已安装 CLI 帮助和实际界面为准。设计交接截图只用于说明，不代表已完成当前浏览器测试或真实外部导出验证。

本文件及相邻中文参考是可安装英文 skill 的完整中文审阅版；实际安装入口位于 `skills/yuplus-visualization/SKILL.md`。
