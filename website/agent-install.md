# Yu+：Agent 安装与启动指南

本文件供收到用户“安装、升级并启动 Yu+”请求的 Agent 阅读。完成下载、校验、安装、检查并打开本地应用；保留用户已有项目。遇到安装冲突或认证缺失时说明具体问题，不把安装流程扩展成项目内容操作。

## 当前发行版与可信来源

- 支持平台：macOS。
- GitHub Release：**v0.3.25**；Python 包 `yuplus-local` 的版本为 **0.3.25**，两者对应同一发行版。
- 官方仓库：https://github.com/Cedar-Zhang-OUTPUT/YuPlus
- 发布说明：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/tag/v0.3.25
- 安装包：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.3.25/YuPlus-v0.3.25.tar.gz
- 校验文件：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.3.25/SHA256SUMS.txt
- 安装包 SHA-256：`0740432be7bbf2779214d1fd0b3a5b5c42693b992210fc94abe58e9ed0b73c31`

固定下载上述版本。不要将 main 分支、旧开发目录或演示数据冒充正式安装。版本发布后如发现错误，报告具体问题，不改写原发布包或擅自修改应用绕过校验。

v0.3.25 新增整项目、单个 draft/Review 对象、原始资料和案例库登记的硬删除；默认仅预览，执行需匹配目标与计划，当前/历史引用会阻止断链。原有软删除与恢复保留。硬删除不会删除飞书内容、外部原件、共用文件或已有备份，整项目删除会清理对应画板缓存。策划文档空状态新增“复制开始整理指令”，按 Skill 整理已有信息并建立或复用飞书协作文档。

创意方案与创意评审/反馈信息保持原有结构。策划文档包括主策 Debrief、项目推进安排、创意方案、创意评审记录与共用客户 Q&A。显示编号按目录顺序连续排列 D01–D25、R01–R05；内部类型键、对象 ID 和历史关系不变，Agent 用真实 ID 操作。

用户进入第二场景时，Agent 保存本地成果并创建或复用项目飞书协作文档，页面常驻文档链接。服务运行时每 60 秒检查绑定文档；远端变化由 Agent 先写入 draft，再更新相关 Review。自动整理需实际宿主任务，建议五分钟且遵守用户设置与宿主限制；同章节两端竞争修改需用户选择，可能丢失评论或素材时暂停替换。安装升级本身不建立文档或新定时任务，也不吸收项目内容。

数据库升级为 schema 10，迁移前自动完整备份，保留现有项目、来源、对象和历史。两份 Skill 同步更新；按需读取 references/collaboration.md 和 references/review-structure.md。原有案例分析画板、头像、案例库与群聊能力保留。内置 18 个已确认案例库源（1 个飞书共享文件夹、17 个网站），每个工作空间只初始化一次。案例库不保存正文、附件、目录清单或搜索索引，移除与恢复只影响本地登记。

## 1. 识别已有环境

检查操作系统；不是 macOS 时说明当前支持范围并停止安装，不自动迁移系统或应用。

先查已知 Yu+ 安装与安装记录。默认应用目录是 `~/.local/share/yuplus-app`，正式数据目录是 `~/.local/share/yuplus`，默认 Skill 目录为 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）。自定义安装应沿用用户已有 `installation.json` 中的实际路径，而不是另建空库。

如已有同版本安装、两份 Skill 和健康的对应服务，可直接检查并复用，不必重新下载安装。可用安装记录中的 Python 查询包版本：

```sh
"/实际安装路径/venv/bin/python" -c 'from importlib.metadata import version; print(version("yuplus-local"))'
```

上面的路径是占位示意，不能原样执行。CLI 没有 `--version` 命令。已有更新版本时不自动降级。

## 2. 下载与校验

新建独立下载目录，在该目录中执行以下命令，检查每一步的退出码：

```sh
curl --fail --location --proto '=https' --tlsv1.2 \
  https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.3.25/YuPlus-v0.3.25.tar.gz \
  --output YuPlus-v0.3.25.tar.gz
curl --fail --location --proto '=https' --tlsv1.2 \
  https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.3.25/SHA256SUMS.txt \
  --output SHA256SUMS.txt
shasum -a 256 -c SHA256SUMS.txt
```

同时核对计算出的摘要与本文件上面的固定摘要。下载或校验失败时停止执行，不忽略错误继续解压。校验成功后：

```sh
tar -xzf YuPlus-v0.3.25.tar.gz
cd YuPlus-v0.3.25
```

读取包内 README.md 及安装入口说明。安装包包含 CLI 源码、前端静态资源、两份 Skill 和安装器，不需要另外搭建数据库服务或 Node 前端服务。

## 3. 统一安装

首次默认安装执行：

```sh
./install.sh
```

已有自定义安装时，显式传入其应用前缀，例如 `./install.sh --prefix '/实际应用目录'`；安装器会沿用该前缀安装记录中的数据和 Skill 目录。仅在用户有意选择新位置时传 `--data-dir` 或 `--skills-dir`，不指向 `.preview` 或验收目录。

从旧版本升级或确实需要重装时，先用旧安装记录中的 CLI 显式传入已核验的 `--data-dir DIR`，执行 `backup create --output NEW_BACKUP_DIR --json`，将数据库和材料备份到与数据目录分开的新目录。备份失败则保留旧安装并处理具体问题，不继续升级。随后执行 `status --json` 和 `stop --json`，检查停止结果；安装完成后对同一目录重新 `start`。v0.3.25 不会自动重启已运行的服务，健康接口也不报告代码版本，不能凭安装成功就认定旧进程已经换成新代码。无法验证或停止旧服务时保留现场，报告具体问题，不按端口强杀进程。

v0.3.25 会复用已有的 `PREFIX/venv`；`--python` 和 `--managed-python` 不会重建它。若现有环境损坏或 Python/SQLite 不达标，不要反复对原前缀重装。保留旧安装，选择一个不存在的新应用前缀，并显式传入原数据目录与原 Skill 目录；这会沿用项目数据并让未修改的托管 Skill 指向新 CLI。执行前说明新应用位置；若涉及已修改的 Skill，则按下文冲突规则处理。旧服务无法停止时先报告，避免两套服务混用。

安装入口会复用满足 Python ≥3.12、SQLite ≥3.51.3 的运行环境；缺少时通过官方 uv 安装器准备私有 Python。之后安装 `yuplus-local`、`yuplus` 与 `yuplus-visualization` 两份 Skill，初始化数据目录并检查飞书认证。需要网络下载运行时与依赖；不修改 shell 配置。

检查退出码以及安装输出中的 `ok`、`cli`、`data_dir`、`skills_dir` 和 `feishu`。不要把日志中的某条成功提示当成整个安装成功。安装输出不会把 CLI 加入 PATH，后续用返回的绝对路径。

如果已有 Skill 是符号链接、非安装器管理或包含用户修改，安装器会拒绝覆盖。保留这些文件，说明具体路径和冲突，由用户选择处理方式。不要先删除旧 Skill 再重试。

升级 schema 1–9 的旧数据库时，v0.3.25 首次访问会迁移到 schema 10，并在数据目录旁的 `数据目录名-migration-backups` 中保存迁移前的完整备份。保留升级前备份；若需要回退旧程序，将该备份恢复到一个新数据目录，不让旧程序直接操作已迁移的 schema 10 库。安装后查询包版本应为 `0.3.25`，并确认 `doctor` 返回 `schema_version: 10`。

## 4. 读取已安装 Skill，并检查环境

确认 CLI 帮助包含 `project purge`、`draft purge`、`review purge`、`source purge`、`library purge`，以及安装后的 Skill `references/deletion.md`；按需用 Skill 的 `inspect_contract.py command project.purge` 等查询 CLI 所带契约。只检查命令与文件是否存在；安装升级不执行硬删除。只有用户明确要求永久删除具体内容时才读取删除流程：先预览、处理真实宿主任务和引用阻塞，再按同一计划执行；`complete=false` 时按原请求重试，不声称清理完成。

读取两份已安装 Skill 的 `installation.json`，取得真实 CLI、Python 和数据目录；核对它们与应用安装记录一致。读取 `yuplus/SKILL.md` 与 `yuplus-visualization/SKILL.md`，按主文件指引读取当前步骤需要的参考文档，避免重复载入已读内容。升级后刷新当前会话中旧版 Skill 指引；确认 `yuplus/references/review-structure.md` 与 `references/deletion.md` 已随安装更新，分别在整理/纠正成果、删除/重新启用时按需读取。确认 `yuplus/references/export.md` 已随安装更新，编写飞书正文及素材时按需读取。确认 `references/collaboration.md` 已安装；CLI 帮助应包含 `collab create/pull/prepare/push/accept/resolve/schedule/scheduler-bind`。旧独立导出记录仍可用 `export record` 与 `export list` 操作。安装或升级本身不导出文档、不创建测试记录。确认 `yuplus/references/case-library.md` 已随安装更新；登记、查找、移除或恢复案例库时再按需读取。CLI 帮助应包含 `library add/list/show/update/delete/restore` 对应命令。安装或升级会一次性初始化内置案例库登记，Agent 用 `library list` 检查结果即可，不另行重复添加，也不读取案例内容。确认 `yuplus/references/case-research.md`、`references/appearance.md` 随安装更新，CLI 帮助包含 `research create/update/list/show/preview` 和 `logo show/set/reset`。安装或升级本身不创建研究或飞书画板、不改头像。找案例依赖已安装的 `lark-doc`、`lark-whiteboard` 及其实际所需能力，正常预览刷新由本地程序执行，无需 Agent 定时任务。新 Skill 尚未被当前会话自动发现时，可直接读取已安装文件继续。`docs/skills/` 中的中文副本仅供用户审阅，不安装，也不作为 Agent 执行参考读取。

飞书能力依赖本机 `lark-cli`。如已存在，使用可用的 `lark-shared` 指引检查认证；无 Skill 时先查 CLI 自身帮助，不猜命令。缺少飞书 CLI 或未登录时明确告知，但继续完成本地功能的启动。不要擅自安装飞书、替用户登录或扩大权限，不输出凭据。

使用安装输出中的实际 CLI 执行 `doctor --json`，显式加 `--data-dir` 指向已核验的正式数据目录，核对返回的绝对 `data_dir`。CLI 的 `YUPLUS_DATA_DIR` 环境变量优先于安装记录，因此安装检查、停止和启动命令都显式指定目标目录，避免误用环境中残留的验收目录。

## 5. 启动并打开真实应用

以下 `CLI` 表示安装输出里的完整可执行文件路径，`DATA_DIR` 表示已核验的数据目录；执行时替换并正确引用两条路径：

```text
CLI --data-dir DATA_DIR doctor --json
CLI --data-dir DATA_DIR start --json
CLI --data-dir DATA_DIR status --json
```

核对命令退出码、`ok`、返回的数据目录与实际 URL。请求该 URL 的 `/api/health`，确认 `mode: live`、数据目录、PID、实例身份和启动结果一致，再通过 Codex 当前可用的浏览器工具打开它。没有浏览器工具时提供核验后的链接，不声称已经打开。

`start` 会启动或复用对应的托管服务；`status` 找回地址；`stop` 仅停止经身份核验的托管服务。`serve --port 0` 是前台备用方式，需保持进程存活。不要猜测固定端口，不运行 Node 演示页面，也不终止其他进程来抢占端口。

每次新服务启动会后台检查已保存飞书来源，复用服务不会重新执行这次启动扫描。已启用的协作文档观察会在服务运行期间每 60 秒检查一次。检查结果通过 CLI 和刷新后的页面查看；协作文档检查保存变化观察记录，其他来源检查保存远端状态；两者都不会自动调用 AI 或改写项目内容。安装任务不包含同步用户项目；只有用户授权相关维护时，才按 Skill 读取新版来源、修改 draft，再更新相关 review。

## 6. 群聊监控的安装边界

v0.3.25 提供 `monitor` 命令和监控面板。确认安装后的 CLI 帮助包含该命令，并按需读取正式 Skill 的 `references/chat-monitoring.md`。只有用户明确指定项目群并要求监控时，才核实群身份、绑定项目并通过当前 Codex 宿主的原生定时工具建立任务。安装或升级本身不创建监控、不读取真实群消息、不创建测试定时任务。

默认间隔60分钟，可按用户要求调整；首次收集全部可访问历史，再按时间顺序维护 draft 和已有受影响 review。没有宿主定时工具时只能手动同步，不宣称自动检查已接通。真实群聊与定时唤起需在用户指定目标后验收；已保存调度回执不等于真实运行成功。

## 7. 协作文档的安装边界

升级不会把已有策划文档直接发布到飞书。用户让 Agent 进入第二场景或明确接通协作时，再按 references/collaboration.md 创建/复用文档并建立宿主真实定时任务；不能把 scheduler-bind 回执当成已经创建任务。旧定时任务存在时先核实并复用，避免重复执行。电脑休眠、离线或宿主关闭时不保证 Agent 运行。

恢复备份后，协作文档观察暂停，调度回执清空。先核实宿主实际任务，避免恢复副本和原库同时维护一份文档，再决定启用。

## 8. 交付与开始项目

报告已安装版本、实际数据目录、服务地址、两份 Skill 状态及飞书可用性。无需要求用户手动准备 Python/SQLite 或手动链接 Skill。

查询已有项目供用户选择；没有项目时询问项目名称和第一份材料。不要创建演示项目或导入测试材料。后续遵循已安装 Skill：信息收集写入 draft；信息整理基于已有对象形成 review；任何反馈先改 draft 再改 review，保留来源、关联和决策历史。

不必一次读完整历史或收齐资料才能进入整理。只有实际项目协作回复才使用 Skill 的“本次读取／本次修改／下一步建议”收尾，不将其应用于软件开发对话。
