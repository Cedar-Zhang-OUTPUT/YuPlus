# Yu+

Yu+ 是供 Agent 使用的本地项目资料 CLI。当前实现覆盖创建多个项目、收录材料、修改 draft、准备与发布 review，以及来源、对象和决策历史的查询。它保存分析结果及其依据；材料读取和内容分析由 Codex 中的 Agent 完成。

每个数据目录使用一份 SQLite 数据库和一个按 SHA-256 寻址的本地文件池，无需运行数据库或对象存储服务。前端界面暂未接入。

## 安装

要求 Python ≥ 3.12，且该 Python 实际链接的 SQLite ≥ 3.51.3。安装命令在本仓库目录执行：

```sh
python3 -c 'import sys, sqlite3; print(sys.version); print("SQLite", sqlite3.sqlite_version)'
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/yu --data-dir .local/yuplus doctor --json
```

SQLite 版本不满足时，需选择带有较新 SQLite 的 Python 后重新建立虚拟环境；安装 Python 包不会替换 Python 所链接的 SQLite。

安装后可用 `.venv/bin/yu`；仓库中的 `./yu` 也提供入口。下文使用 `./yu`。默认数据目录为 `~/.local/share/yuplus`，开发和演示建议显式提供独立的 `--data-dir`。

## Yu+ Agent Skill

可安装的 Skill 在 [skills/yuplus](skills/yuplus/SKILL.md)，用于主策实际推进项目。它包含按需恢复上下文、飞书/本地/口述材料收录、draft 与 review 的因果更新规则，以及每轮结束时的下一步引导；不应用于 Yu+ 软件开发对话。

当前只有信息收集、信息整理两个场景；draft 与 review 是信息整理场景内的阶段。场景可往返，不设信息完整度门槛。

- [完整中文审阅版](docs/skills/yuplus/SKILL.zh-CN.md)：主文件、材料处理和 CLI 参考的中文译文。
- [对象属性与成果关系](skills/yuplus/references/objects.md)：23 类 draft、内部编写依据，以及五类成果的依赖和回改位置。
- [验证记录](docs/skills/yuplus/validation.md)：实际执行范围及尚未验证的边界。

在本仓库根目录执行以下命令可将 Skill 链接到本机 Codex 的 skills 目录；目标已存在时命令会停止，避免覆盖其他版本：

```sh
python3 - <<'PY'
import os
from pathlib import Path
source = (Path.cwd() / 'skills' / 'yuplus').resolve()
assert (source / 'SKILL.md').is_file(), '请在 YuPlus 仓库根目录运行'
destination = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills' / 'yuplus'
destination.parent.mkdir(parents=True, exist_ok=True)
destination.symlink_to(source, target_is_directory=True)
print(destination)
PY
```

Skill 被 Codex 发现后，可用 `$yuplus` 明确调用。安装 Skill 不会安装应用、创建项目或登录飞书。首次项目使用时，Agent 按 Skill 检查实际 CLI 环境；飞书不可用仍可处理本地材料。

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

`--input -` 从标准输入读取 UTF-8 JSON。写命令需要 `--request-id`；读取命令不需要。`--json` 下标准输出只有一个结果对象，错误同样使用 JSON，并以非零退出码结束。参数可以放在命令路径之前或之后。

`review.prepare` 返回当前依据和受影响内容，不调用模型生成文字。Agent 据此组织正文，再通过 `review.publish` 提交。用户要求改已有 review 时，先修改相关 draft；纯措辞要求先保存到 draft 的 `expression_guide`。

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

- 一个数据目录管理多个项目，所有业务操作显式指定项目，拒绝跨项目的证据与对象引用。
- 保存飞书、网页等来源的身份和 Agent 提供的内容；本地文件可复制或登记外部路径；口述保存原话及归属。
- 23 类 draft 对象按需建立，内部条目有稳定 ID；无业务信息完整度门槛。R05 Q&A 使用 D15 的同一份数据。
- 来源快照、draft/review 版本及决策只追加。更新比较基础版本，重放同键同请求返回原回执。
- review 更新校验相关 draft 变更、段落因果履历和依赖有效性；CLI 不判断自然语言的分析是否正确。
- 一个 draft 批次或一次 review 发布分别原子提交。draft 已保存而 review 发布失败时，保留 draft，读取新的依据后继续。

当前未包含可视化界面/浏览器网关、飞书后台自动读取与启动版本扫描、导出、备份/GC 命令。Skill 指导 Agent 使用外部飞书 CLI 读取材料和做首次环境检查，应用本身不提供这些服务。原契约中列出的其他辅助命令（如 archive、diff、relations、review check）也不应视为已经提供；实际命令以 `./yu --help` 为准。

数据库文件与对象池共同组成项目数据。当前没有在线备份命令；不要只复制运行中的 SQLite 主文件来当作完整项目备份。

## 开发和验证

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python docs/superpowers/specs/contracts/v0.1/verify_contracts.py
.venv/bin/python scripts/demo_chain.py
```

测试使用临时目录或内存数据库，不读取个人项目。`tests/test_cli.py` 通过真实 CLI 子进程检查完整链路、项目隔离、历史留存、幂等和机器可读错误；领域测试检查来源、draft、review 的细节约束。契约校验只验证 Schema/DDL/示例，不替代业务测试。

实现入口在 `src/yuplus/`，安装包带有自己的 `contracts/` 资源。设计基线见：

- [对象关系](docs/superpowers/specs/2026-10-13-yuplus-object-relations-design.md)
- [数据库与 CLI 契约](docs/superpowers/specs/2026-10-13-yuplus-data-cli-contract.md)
- [最小链路实施计划](docs/superpowers/plans/2026-10-13-yuplus-minimal-cli.md)

当前实现仍是最小链路版本，适合本地试用和继续开发；尚未验证跨机器分发安装或异常断电恢复。
