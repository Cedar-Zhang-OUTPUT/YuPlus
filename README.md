# Yu+

[官网与 Agent 安装提示词](https://cedar-zhang-output.github.io/YuPlus/) · [下载 v0.3.20](https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/tag/v0.3.20)

Yu+ 是供 Agent 使用的本地项目资料 CLI。当前实现覆盖创建多个项目、收录材料、修改 draft、准备与发布 review，以及来源、对象和决策历史的查询。它保存分析结果及其依据；材料读取和内容分析由 Codex 中的 Agent 完成。

每个数据目录使用一份 SQLite 数据库和一个按 SHA-256 寻址的本地文件池，无需运行数据库或对象存储服务。已提供仅绑定本机的 Python 只读网关，沿用已交付 UI，读取真实项目及文件；正式运行无需 Node.js。

## 安装与打开（首版 macOS）

在可信的本地代码包/仓库目录执行：

```sh
./install.sh
```

入口先检查本机 Python/SQLite；缺少合适环境时使用 uv 官方安装器准备私有 Python，不修改 shell 配置。随后建立独立环境、安装应用和两份 Codex Skill、初始化固定数据目录，并检查飞书认证。默认应用在 `~/.local/share/yuplus-app`，数据在 `~/.local/share/yuplus`。返回 JSON 中的实际 CLI、数据目录和启动命令；可用 `--prefix`、`--data-dir`、`--skills-dir` 改位置。不会覆盖非安装器管理或已修改的 Skill，也不会代替用户登录飞书。缺少飞书仍可使用本地材料。

```sh
~/.local/share/yuplus-app/venv/bin/yu start --json
~/.local/share/yuplus-app/venv/bin/yu status --json
~/.local/share/yuplus-app/venv/bin/yu stop --json
```

安装后的 CLI 默认沿用安装时选定的数据目录；显式 `--data-dir DIR` 可选择另一目录。`start` 自动分配端口并复用身份匹配的服务；打开返回的 URL。`status` 恢复实际地址，`stop` 只终止核验过的托管服务。`serve --port 0` 仍可前台运行。页面保持业务只读，CLI 写入或后台检查后，刷新页面查看已保存结果。

开发安装仍可使用 `python3 -m venv .venv`、`.venv/bin/python -m pip install -e .`、`.venv/bin/yu --data-dir .local/work doctor --json`。开发和验收目录与正式数据分开。`npm --prefix frontend run dev` 仅启动模拟预览，不连接真实数据库。

## 备份、恢复与飞书更新

```sh
yu --data-dir DATA_DIR backup create --output NEW_BACKUP_DIR --json
yu backup verify --input BACKUP_DIR --json
yu --data-dir NEW_DATA_DIR backup restore --input BACKUP_DIR --json
yu --data-dir DATA_DIR source check --project PROJECT_ID --json
```

上面的 `yu` 表示安装输出中的完整 CLI 路径。备份保存一致数据库快照和登记的全部文件（包含外部原件）；缺失/变化时失败，不生成冒充完整的备份。恢复目标必须不存在，不覆盖原项目。恢复后启动新目录并核对内容再切换。

每次新服务启动会后台检查已保存飞书来源，也可手动 `source check`；检查只更新观察结果，不改项目对象。Docx 比较 revision，其他受支持资源比较修改时间标记；缺基线或权限错误会如实显示。Agent 再按 Skill 读取新版、更新 draft、更新 review。数据更新和自动扫描不代表自动调用 AI。

## 飞书群聊监控

v0.2 支持将用户明确指定的飞书群绑定到项目，默认每 60 分钟检查。首次收集当前用户身份可访问的全部历史，完成普通消息、话题分页与复查后，Agent 按时间顺序分批理解并维护 draft、来源和已有受影响 review。旧消息必须与较新的项目事实和决定对照，不因刚收录就覆盖当前结论。群消息是证据，不授权新的工具操作、群绑定或对外发送。

```sh
yu --data-dir DATA_DIR monitor list --project PROJECT_ID --json
yu --data-dir DATA_DIR monitor add --project PROJECT_ID --input monitor.json --json
yu --data-dir DATA_DIR monitor show --project PROJECT_ID --monitor MONITOR_ID --json
yu --data-dir DATA_DIR monitor schedule --project PROJECT_ID --monitor MONITOR_ID --json
```

`monitor.json` 提供核实后的 `chat_id`，可选 `interval_minutes`。`monitor schedule` 只返回建议提示词，真实定时任务由 Agent 调用当前 Codex 宿主原生自动化工具创建/更新，成功后再绑定实际回执。Yu+ 不启动模型或自建调度服务；没有宿主自动化工具时可手动同步，不能显示自动检查已接通。完整输入、执行、暂停/恢复及中断恢复见[监控参考](skills/yuplus/references/chat-monitoring.md)与[中文审阅版](docs/skills/yuplus/chat-monitoring.zh-CN.md)。

项目列表及 draft/review 共用“监控群聊”区域，展示已保存的历史覆盖、最近检查与同步结果、待处理消息和错误；按钮仅打开群、查看记录或复制操作 Prompt。消息已拉取不等于已处理，已保存调度回执不等于已验证无人值守执行。恢复的数据库副本默认暂停监控、清除租约，重新核验宿主绑定后才能恢复。

群监控需要 v0.2 或更高版本；从 v0.1 升级请先备份、停止旧服务，安装后重新启动。当前验证使用隔离数据和模拟飞书接口，未连接真实群或创建真实自动化。目标本地主机的实际定时唤起、无人交互权限及认证仍需验证；电脑休眠、离线或关闭 Codex 时不保证执行。API 不可见的历史、话题及附件不能声称已读取。

## Yu+ Agent Skill

可安装的 Skill 在 [skills/yuplus](skills/yuplus/SKILL.md)，用于主策实际推进项目。它包含按需恢复上下文、飞书/本地/口述材料收录、draft 与 review 的因果更新规则，以及每轮结束时的下一步引导；不应用于 Yu+ 软件开发对话。

当前只有信息收集（draft）、信息整理（review）两个场景：收集时将材料中的信息落到 draft 对象；整理时由 AI 根据已有信息组织、改写 review 成果。场景可往返，不设信息完整度门槛。

- [完整中文审阅版](docs/skills/yuplus/SKILL.zh-CN.md)：主文件、材料处理和 CLI 参考的中文译文。
- [对象属性与成果关系](skills/yuplus/references/objects.md)：24 类 draft、内部编写依据，以及五类成果的依赖和回改位置。
- [群聊监控与失败恢复](skills/yuplus/references/chat-monitoring.md)：真实调度绑定、全量可访问历史、按时间分批处理、回执重放与静默检查。
- [业务 Skill 验证记录](docs/skills/yuplus/validation.md)。
- [可视化使用 Skill](skills/yuplus-visualization/SKILL.md) 及[完整中文版本](docs/skills/yuplus-visualization/SKILL.zh-CN.md)：启动服务、导航、来源/版本/差异、复制 Prompt 和故障处理。
- [完整集成验收](docs/validation/2026-10-16-live-integration.md)。
- [安装、备份恢复与来源检查验证](docs/validation/2026-10-16-readiness.md)。

统一安装入口会同时安装两份 Skill，不需要手动链接。Skill 被 Codex 发现后，可用 `$yuplus` 明确调用；首次项目使用时 Agent 读取安装记录并按需检查环境。飞书不可用仍可处理本地材料。

中文 Skill 仅保存在 `docs/skills/` 供人工审阅；安装目录只包含英文 Skill 及其运行参考，英文路由不加载中文副本。

Skill 中的 `scripts/inspect_contract.py` 使用安装了 Yu+ 的 Python，只读取包内契约，不打开数据库。例如：

```sh
.venv/bin/python skills/yuplus/scripts/inspect_contract.py command draft.apply --type budget_range
```

## 运行完整演示

```sh
# 在临时目录运行，完成后自动清理
.venv/bin/python scripts/demo_chain.py

# 保留数据库和材料副本，供后续查看
.venv/bin/python scripts/demo_chain.py --data-dir .local/demo

# 通过已安装的命令入口执行同一演示
.venv/bin/python scripts/demo_chain.py --cli .venv/bin/yu --data-dir .local/installed-demo
```

演示使用命令实际返回的 ID，完整执行：

1. 创建项目，收录模拟飞书材料中的“预算 100 万”。
2. 将有来源的预算条目写入 draft，再组织第一版 Debrief。
3. 验证直接改写 review 会被拒绝。
4. 收录用户“按 60 万推进”的原话，修改 draft 并保存决策。
5. 重新准备、发布 review，验证同一请求重放不制造新版本。
6. 复制本地文件，删除演示原路径后验证重放与留存。
7. 查询原始材料、旧 draft、当前成果和决策，检查历史仍可追溯。

演示不会访问飞书，示例地址不是实际材料来源。每次运行新建一个项目，不修改已有项目。指定目录时，演示结束会打印所有关键 ID；省略目录时这些 ID 随临时数据一起清理。

## CLI 的最小使用方式

```sh
./yu --data-dir .local/work project create --name '城市展项目' --request-id project_001 --json
./yu --data-dir .local/work project list --json
```

从创建结果的 `data.project_id` 取得真实 ID。四个核心命令的 JSON 输入见[契约示例](docs/superpowers/specs/contracts/v0.1/examples/README.md)；示例中的来源、对象和版本 ID 是说明性占位值，需替换为前一命令的实际输出。

```sh
./yu --data-dir .local/work source import --project prj_EXAMPLE --request-id source_001 --input source.json --json
./yu --data-dir .local/work draft apply --project prj_EXAMPLE --request-id draft_001 --input draft.json --json
./yu --data-dir .local/work review prepare --project prj_EXAMPLE --input prepare.json --json
./yu --data-dir .local/work review publish --project prj_EXAMPLE --request-id review_001 --input review.json --json
```

`--input -` 从标准输入读取 UTF-8 JSON。上述核心业务写命令需要 `--request-id`；读取命令不需要。监控流程使用自身的配置版本、run/token 与稳定 step_key，内部生成并复用业务请求身份。`--json` 下标准输出只有一个结果对象，错误同样使用 JSON，并以非零退出码结束。参数可以放在命令路径之前或之后。

`review.prepare` 返回当前依据和受影响内容，不调用模型生成文字。Agent 据此组织正文，再通过 `review.publish` 提交。用户要求改已有 review 时，先修改相关 draft；纯措辞要求先保存到 draft 的 `expression_guide`。

### 项目重命名

先用 `project show --project PROJECT_ID --json` 读取名称和 `metadata_version`，再执行：

```sh
./yu --data-dir .local/work project rename --project PROJECT_ID --name '新项目名称' --base-version METADATA_VERSION --request-id rename_001 --json
```

保留项目 ID、来源、draft/review、群监控及历史，记录新旧名称。名称不能为空；同名修改不增加版本；版本冲突时重新读取并核对。刷新页面即可显示新名称。

### 项目删除

```sh
./yu --data-dir .local/work project delete --project PROJECT_ID --base-version METADATA_VERSION --request-id delete_001 --json
./yu --data-dir .local/work project list --include-deleted --json
```

版本来自 `project show`。软删除后，正常列表与页面隐藏项目、禁止业务写入，本地群监控暂停；保留材料和历史，不清除共享文件池。回执的 `scheduler_actions` 需由 Agent 使用宿主工具同步处理，不能把本地暂停当成已停宿主任务。本版没有永久清除/恢复命令。

### 查询和按需恢复上下文

```sh
./yu --data-dir .local/work project show --project prj_EXAMPLE --json
./yu --data-dir .local/work source list --project prj_EXAMPLE --json
./yu --data-dir .local/work source show --project prj_EXAMPLE --source src_EXAMPLE --json
./yu --data-dir .local/work draft list --project prj_EXAMPLE --json
./yu --data-dir .local/work draft show --project prj_EXAMPLE --object obj_EXAMPLE --json
./yu --data-dir .local/work review list --project prj_EXAMPLE --json
./yu --data-dir .local/work review show --project prj_EXAMPLE --object obj_EXAMPLE --json
./yu --data-dir .local/work changes list --project prj_EXAMPLE --limit 20 --json
./yu --data-dir .local/work decisions list --project prj_EXAMPLE --limit 20 --json
./yu --data-dir .local/work types show --type budget_range --json
```

`source show` 默认返回元信息和附件清单，加 `--include-body` 才读取正文；可加 `--snapshot` 查看指定来源快照。`draft show` / `review show` 可加 `--revision` 查看历史版本。`changes list` 与 `decisions list` 的 `next_cursor` 可原样传给下一次 `--after-cursor`，游标绑定项目与命令，同一批次的多条决策也不会漏页。该参数也接受明确的数字历史序号，用于从一次已知变更后增量读取。不要每轮重新加载全项目历史。

## 已实现的边界

- 一个数据目录管理多个项目，项目业务操作显式指定项目，拒绝跨项目的证据与对象引用。
- 保存飞书、网页等来源的身份和 Agent 提供的内容；本地文件可复制或登记外部路径；口述保存原话及归属。
- 24 类 draft 对象按需建立，内部条目有稳定 ID；无业务信息完整度门槛。D24“开放性问题”保留尚待探索、讨论或判断的议题；D15 保存具体客户澄清问答，R05 使用 D15 的同一份数据。
- v0.3.16 新增工作空间案例库登记（独立于项目）：`library add/list/show/update/delete/restore`，只保存名称、链接及登记元数据；内容由 Agent 使用飞书 CLI 按需查找，不在 Yu+ 缓存。删除与恢复只影响本地登记，不改变飞书文件夹。
- v0.3.16 将旧库升级为 schema 4，迁移前保存完整备份；不自动搬迁原有 Q&A 内容。升级前停止旧服务，安装后重启，回退时恢复升级前备份到新目录。
- 来源快照、draft/review 版本及决策只追加。更新比较基础版本，重放同键同请求返回原回执。
- review 更新校验相关 draft 变更、段落因果履历和依赖有效性；CLI 不判断自然语言的分析是否正确。
- 一个 draft 批次或一次 review 发布分别原子提交。draft 已保存而 review 发布失败时，保留 draft，读取新的依据后继续。
- 群监控保存分页、不可变消息版本、步骤回执和项目执行租约；重试复用同一步骤，先修复未完成 review，不重复添加决定。业务判断由 Agent 完成，CLI 校验身份、版本、证据与因果约束。

已提供安装入口、托管启动/重新打开、完整备份恢复，以及启动时的飞书来源检查。说明见[运维参考](skills/yuplus/references/operations.md)及[中文版本](docs/skills/yuplus/operations.zh-CN.md)。来源检查仅更新观察结果，Agent 根据授权维护源快照、draft 和 review。

实际命令以 `yu --help` 为准。

数据库与材料池共同构成项目。请使用完整备份命令，不要只复制运行中的 SQLite 主文件。

## 完整导出与真实集成验收

```sh
.venv/bin/python -m yuplus.export_bundle --data-dir .local/work --project PROJECT_ID --output .local/export
```

输出 `review.md` 和 `manifest.json`，包括全部当前成果实例、共用 Q&A、引用/当前 draft 版本及来源全文。输出目录必须在业务数据目录之外。该步骤只准备本地文件，不上传媒体，也不创建飞书文档。按 Skill 调飞书 CLI 创建新文档并回读验证后，才能报告远端导出成功。

可重复的合成资料验收（全部业务写入经过真实 CLI）：

```sh
.venv/bin/python scripts/live_acceptance.py seed --root .preview/my-acceptance
.venv/bin/yu --data-dir .preview/my-acceptance/data serve --port 0 --json
# 在另一终端填写启动结果的实际 URL；此时可先在浏览器检查旧/新依据差异
.venv/bin/python scripts/live_acceptance.py finish --root .preview/my-acceptance --url http://127.0.0.1:ACTUAL_PORT
```

每次选择新的验收目录；脚本不访问飞书、不读个人项目。覆盖两个项目隔离、真实文本/图片、日/分钟时间、5 个成果实例、同源 Q&A、拒绝跳过 draft、条目级影响、更新与历史留存、完整本地导出。远端飞书验证是另行执行的外部验收，详见验证记录。

## 开发和验证

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python docs/superpowers/specs/contracts/v0.1/verify_contracts.py
.venv/bin/python scripts/demo_chain.py
```

测试使用临时目录或内存数据库，不读取个人项目。`tests/test_cli.py` 通过真实 CLI 子进程检查完整链路、项目隔离、历史留存、幂等和机器可读错误；领域测试检查来源、draft、review 的细节约束。契约校验只验证 Schema/DDL/示例，不替代业务测试。

实现入口在 `src/yuplus/`，安装包带有自己的 `contracts/` 资源。设计基线见：

- [对象关系](docs/superpowers/specs/2026-10-13-yuplus-object-relations-design.md)
- [可视化界面信息展示 Spec](docs/superpowers/specs/2026-10-13-yuplus-visualization-information-spec.md)：完整对象、来源、关联与历史的展示需求，用于选择 UI example，不规定布局和风格。
- [数据库与 CLI 契约](docs/superpowers/specs/2026-10-13-yuplus-data-cli-contract.md)
- [最小链路实施计划](docs/superpowers/plans/2026-10-13-yuplus-minimal-cli.md)
- [ADR-0001：找案例画板预览与程序自动刷新](docs/adr/0001-case-finding-whiteboard-preview.md)：已接受、待实现，与现有项目对象无直接关联。

首版面向 macOS 本地使用。开发侧验证安装、重启、备份恢复和来源检查；真实 Agent 使用验收以及跨机器分发/升级验收由用户在发布后进行，不宣称已完成。

### 子目、对象与来源删除

子目改写/删除使用 `draft apply` 的 `set_items`/`remove_items`；Review 段落使用 `review publish` 的 `set_blocks`/`remove_blocks`，保留先 draft 后 review 的因果要求。整份对象及来源支持 `draft delete`、`review delete`、`source delete`（`--input` JSON），均为保留文件和历史的软删除。删除最后一个 Review 段落会隐藏空成果。`list --include-deleted` 查询保留记录；对应 `restore` 命令可重新启用原身份，draft/Review 的当前空内容需另按依据写回。详细契约与用法见 [Skill 删除指引](skills/yuplus/references/deletion.md)。

飞书成果导出使用 Skill 的 `references/export.md` 完成准备、写入和回读；核验后由 `yu export record` 保存标题、链接、版本和时间，`yu export list --project ID` 查询。Review 页的历史图标只展示已保存记录。

案例库支持 `kind=feishu_folder` 和 `kind=website` 两种源，均仅保存类型、名称和链接。前端提供两条独立的新增 Prompt；网站通过浏览器/网页工具按需查找，飞书文件夹通过飞书 CLI 查找。`library delete/restore` 均只影响本地登记。schema 5 为旧记录补充飞书文件夹类型，迁移前自动完整备份，保留原项目和案例库身份。

## 找案例与工作空间头像（v0.3.20）

找案例独立于 draft/review：`research create/update/list/show/preview` 保存研究轮次和飞书文档/画板定位。新研究新建 vN，同轮补充和用户飞书编辑沿用原画板；幂等请求避免重试产生重复轮次。案例正文、图片及详细索引在飞书，Yu+ 不建立本地案例内容库。

Agent 按 Skill 用飞书 CLI 创建和修改画板；本地服务仅导出预览。前端提供历史切换、缩放、平移和新标签页跳转；可见画板每 60 秒刷新，离开后停止，失败保留旧图，权限错误暂停。预览缓存位于系统缓存目录，不进入业务库或备份。创建/绑定新研究后刷新页面读取新历史。

左上角头像菜单可复制更改提示词；Agent 压缩图片后使用 `logo set`，支持 `logo show/reset`。头像随数据库备份。

当前 schema 7。从 schema 1–6 升级前自动完整备份；保留原项目、来源、对象和历史。升级前先备份、停止旧服务，安装后沿用原数据目录重启。两份 Skill 同步更新；中文版本仅供审阅。
