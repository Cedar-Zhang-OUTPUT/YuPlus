# Yu+：Agent 安装与启动指南

本文件供收到用户“安装并启动 Yu+”请求的 Agent 阅读。完成下载、校验、安装、检查并打开本地应用；保留用户已有项目。遇到安装冲突或认证缺失时说明具体问题，不把安装流程扩展成项目内容操作。

## 当前发行版与可信来源

- 支持平台：macOS。
- GitHub Release：**v0.1**；Python 包 `yuplus-local` 的版本为 **0.1.0**，两者是同一版本的不同命名。
- 官方仓库：https://github.com/Cedar-Zhang-OUTPUT/YuPlus
- 发布说明：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/tag/v0.1
- 安装包：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.1/YuPlus-v0.1.tar.gz
- 校验文件：https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.1/SHA256SUMS.txt
- 安装包 SHA-256：`7ad849b8a6c63e0edb3dc840daf89b23a397e4ec66cbbf1779cfc8fcd8d558b4`

固定下载上述版本。不要将 main 分支、旧开发目录或演示数据冒充正式安装。版本发布后如发现错误，报告具体问题，不改写原发布包或擅自修改应用绕过校验。

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
  https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.1/YuPlus-v0.1.tar.gz \
  --output YuPlus-v0.1.tar.gz
curl --fail --location --proto '=https' --tlsv1.2 \
  https://github.com/Cedar-Zhang-OUTPUT/YuPlus/releases/download/v0.1/SHA256SUMS.txt \
  --output SHA256SUMS.txt
shasum -a 256 -c SHA256SUMS.txt
```

同时核对计算出的摘要与本文件上面的固定摘要。下载或校验失败时停止执行，不忽略错误继续解压。校验成功后：

```sh
tar -xzf YuPlus-v0.1.tar.gz
cd YuPlus-v0.1
```

读取包内 README.md 及安装入口说明。安装包包含 CLI 源码、前端静态资源、两份 Skill 和安装器，不需要另外搭建数据库服务或 Node 前端服务。

## 3. 统一安装

首次默认安装执行：

```sh
./install.sh
```

已有自定义安装时，显式传入其应用前缀，例如 `./install.sh --prefix '/实际应用目录'`；安装器会沿用该前缀安装记录中的数据和 Skill 目录。仅在用户有意选择新位置时传 `--data-dir` 或 `--skills-dir`，不指向 `.preview` 或验收目录。

确实需要重装时，先用旧安装记录中的 CLI 显式传入已核验的 `--data-dir DIR`，执行 `status --json`，再执行 `stop --json`，检查停止结果；安装完成后对同一目录重新 `start`。v0.1 不会自动重启已运行的服务，健康接口也不报告代码版本，不能凭安装成功就认定旧进程已经换成新代码。无法验证或停止旧服务时保留现场，报告具体问题，不按端口强杀进程。

v0.1 会复用已有的 `PREFIX/venv`；`--python` 和 `--managed-python` 不会重建它。若现有环境损坏或 Python/SQLite 不达标，不要反复对原前缀重装。保留旧安装，选择一个不存在的新应用前缀，并显式传入原数据目录与原 Skill 目录；这会沿用项目数据并让未修改的托管 Skill 指向新 CLI。执行前说明新应用位置；若涉及已修改的 Skill，则按下文冲突规则处理。旧服务无法停止时先报告，避免两套服务混用。

安装入口会复用满足 Python ≥3.12、SQLite ≥3.51.3 的运行环境；缺少时通过官方 uv 安装器准备私有 Python。之后安装 `yuplus-local`、`yuplus` 与 `yuplus-visualization` 两份 Skill，初始化数据目录并检查飞书认证。需要网络下载运行时与依赖；不修改 shell 配置。

检查退出码以及安装输出中的 `ok`、`cli`、`data_dir`、`skills_dir` 和 `feishu`。不要把日志中的某条成功提示当成整个安装成功。安装输出不会把 CLI 加入 PATH，后续用返回的绝对路径。

如果已有 Skill 是符号链接、非安装器管理或包含用户修改，安装器会拒绝覆盖。保留这些文件，说明具体路径和冲突，由用户选择处理方式。不要先删除旧 Skill 再重试。

## 4. 读取已安装 Skill，并检查环境

读取两份已安装 Skill 的 `installation.json`，取得真实 CLI、Python 和数据目录；核对它们与应用安装记录一致。读取 `yuplus/SKILL.md` 与 `yuplus-visualization/SKILL.md`，按主文件指引读取当前步骤需要的参考文档，避免重复载入已读内容。新 Skill 尚未被当前会话自动发现时，可直接读取已安装文件继续。

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

每次新服务启动会后台检查已保存飞书来源，复用服务不会重新扫描。检查结果通过 CLI 和刷新后的页面查看；检查不会自动调用 AI、收录新版或改写项目内容。安装任务不包含同步用户项目；只有用户授权相关维护时，才按 Skill 读取新版来源、修改 draft，再更新相关 review。

## 6. 交付与开始项目

报告已安装版本、实际数据目录、服务地址、两份 Skill 状态及飞书可用性。无需要求用户手动准备 Python/SQLite 或手动链接 Skill。

查询已有项目供用户选择；没有项目时询问项目名称和第一份材料。不要创建演示项目或导入测试材料。后续遵循已安装 Skill：信息收集写入 draft；信息整理基于已有对象形成 review；任何反馈先改 draft 再改 review，保留来源、关联和决策历史。

不必一次读完整历史或收齐资料才能进入整理。只有实际项目协作回复才使用 Skill 的“本次读取／本次修改／下一步建议”收尾，不将其应用于软件开发对话。
