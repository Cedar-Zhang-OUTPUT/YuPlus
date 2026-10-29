# 安装、恢复与来源检查

对应英文 `references/operations.md`。只读当前任务所需部分，这些运维能力不增加业务场景，也不设阶段准入条件。

## 安装位置与服务

安装后的 Skill 若含 `installation.json`，首次使用时读取其中的 `cli`、`python`、`data_dir`，后续复用。用户选择其他工作目录或复制的真实项目引用指向另一目录时，明确核对；开发 `.preview` 不是正式数据目录。

从可信的本地代码包运行 `./install.sh`，复用合适的 Python，缺少时通过 uv 官方安装器准备独立运行环境，再安装应用及两份 Skill，检查 Python ≥3.12、SQLite ≥3.51.3，初始化选定数据目录并检查飞书认证。可用 `--prefix`、`--skills-dir`、`--data-dir` 指定位置；`--python PATH` 指定已有解释器，`--managed-python` 强制独立环境路径。不修改 shell 配置。拒绝覆盖非安装器管理或已被修改的 Skill；不会代用户安装飞书或登录，认证问题按 lark-shared 处理。首版面向 macOS。

`yu --data-dir DIR start --json` 启动或复用服务；`status` 返回核验后的地址，`stop` 只停止数据目录、PID、实例身份均匹配的服务。`serve --port 0` 保留为前台启动方式。通过可用的 Codex 浏览器工具打开实际地址。每次新服务启动会后台检查来源，复用服务不意味着重新扫描。后台检查或 CLI 写入完成后刷新原页面，查看保存的结果。

## 完整备份与恢复

- `yu --data-dir DIR backup create --output NEW_BACKUP_DIR --json`
- `yu backup verify --input BACKUP_DIR --json`
- `yu --data-dir NEW_DATA_DIR backup restore --input BACKUP_DIR --json`

备份包含一致的 SQLite 快照及全部已登记材料文件，包括外部路径原件。有原件缺失或变化时失败，不宣称部分备份完整。恢复目标必须不存在；校验哈希、数据库完整性和材料覆盖，保留所有身份和历史。外部材料映射到恢复的副本，不改写封存来源。启动恢复目录并核对项目与关键材料后再切换工作；不要只复制运行中的 SQLite 主文件，不删除原数据，也不把 Markdown 导出当备份。

监控记录也进入备份。恢复副本会暂停监控并清除执行租约；明确核验新宿主调度并恢复指定绑定后，才能宣称自动检查可用。不能让原库与恢复副本沿用同一旧调度身份同时执行。数据库升级会保留迁移前数据库快照，但它不能替代上述数据库与材料的完整备份。

## 群监控与宿主准备

用户明确要求监控项目群时，遵循[群聊监控](chat-monitoring.zh-CN.md)。设置时检查目标 Codex 宿主是否提供原生自动化工具，以及它能否无人交互地调用已安装 CLI、访问指定数据目录、以正确飞书用户认证。它们是宿主能力，安装器不创建后台调度服务。没有该工具时只做手动同步，自动检查保持未配置。

默认 60 分钟，首次先收集全部可访问历史再按时间处理。`monitor schedule` 只返回提示词，不创建运行任务；原生工具成功后才保存回执，实际无人值守运行成功后才能确认该执行路径。本地主机必须可用，休眠、离线、关闭 Codex 不保证执行。不读取或编辑私有调度 TOML/数据库来替代宿主工具。

## 飞书来源更新

`source check --project PID --json` 检查项目，加 `--source SID` 检查单个来源；省略项目检查全部已保存飞书来源。`source list` 暴露检查时间、观察结果与错误。检查只记远端变化，不自动收录正文、改写 draft/review，也不制造业务变更记录。

飞书消息来源由监控的消息观察路径处理，不使用文档 revision 检查；普通 `source check` 不等于群同步，不能证明消息最新。

Docx 比较实际 revision；其他受支持资源使用元数据修改时间 `mtime:<latest_modify_time>`。收录这类资源时，将实际取得的标记写入 `snapshot.provenance.remote_marker`。如果内容读取前后标记不同，不能宣称是同一版本的完整快照；不编造标记。缺少可比较的收录基线就是 unknown，接口成功不等于内容未变。已知更新在后续检查失败时仍保留，直到新快照使旧观察失效。飞书失败不阻塞本地工作。

用户要求同步，或更新属于已经授权的项目维护时：按相应 Skill 读取新版，追加真实来源快照，更新相关 draft，再更新依赖 review。不重写无关对象；有冲突时不能把新材料自动当成用户的新决定。纯措辞反馈仍先保存 draft 编写依据。

## 项目重命名

对应英文 `references/cli.md` 的 “Rename a project”。用户要求重命名时，明确已有项目 ID，用 `project show --project PROJECT_ID --json` 读取当前名称和 `metadata_version`，然后执行：

```sh
yu --data-dir DATA_DIR project rename --project PROJECT_ID --name '新项目名称' --base-version METADATA_VERSION --request-id REQUEST_ID --json
```

`--base-version` 使用刚读到的整数 `metadata_version`。名称去除首尾空白后不能为空。返回 `effect`、`project_id`、`name`、`previous_name`、`metadata_version`、`working_scene`、`lifecycle`，变更记录保留新旧名称。与当前名称相同时返回 `noop`，不增加元信息版本。重试复用相同请求 ID 和参数；版本冲突时先重新读取并核对用户意图，再用新请求 ID 提交。

保留项目 ID、材料文件、来源身份、对象版本、群监控绑定与历史。不要新建项目替代，不移动数据目录，也不因重命名而改写 draft/review。成功后刷新原页面，项目列表、面包屑和新复制的引用会使用新名称；历史文档正文及先前已复制或导出的内容保留原有文字。

## 项目删除

仅在用户明确要求删除指定项目时执行；目标有歧义才澄清。读取 `project show` 的当前名称和 `metadata_version`，然后：

```sh
yu --data-dir DATA_DIR project delete --project PROJECT_ID --base-version METADATA_VERSION --request-id REQUEST_ID --json
```

采用软删除，内部 lifecycle 为 `archived`：正常 CLI 列表和页面隐藏项目，禁止业务写入，原子地暂停本地监控并使执行租约失效。保留原文件、对象版本和历史，不释放磁盘，也不删除飞书群/文档。不能递归删除共享数据目录或文件池。`project list --include-deleted --json` 可找回保留的项目身份，`project show` 可显式检查。明确要求硬删除时使用 project purge，按[删除参考](deletion.zh-CN.md)预览并执行。项目没有 restore 命令，不直接修改 SQLite。

返回 `deletion_mode:soft`、`retained_data:true`、新元信息版本及 `scheduler_actions`。后者是已保存的群监控/调度回执，不代表宿主任务已经停掉。沿用用户的删除授权，通过宿主原生自动化工具暂停/移除真实任务；共享任务只移除此项目范围，保留其他项目。宿主不可操作时说明尚待清理的定时任务，本地项目写入已经被禁止，不能宣称宿主任务已停止。不确定是否成功时，用相同请求 ID 和版本重试；版本冲突先重读再用新请求。
