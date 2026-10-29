# 删除子目、对象与来源

用户明确要求删除或重新启用时才读取；已读则复用。使用当前项目和真实版本，不能因收集、整理或升级而自行清理。所有删除保留历史和文件，不直接改 SQLite 或删除共享文件池。

| 用户要求 | CLI 操作 |
| --- | --- |
| 改写 draft 子目 | `draft apply` 的 `set_items` 替换整个指定子目，包括来源和依赖；保留其他子目。 |
| 删除 draft 子目 | `remove_items` 指定真实子目 ID；删光后保留启用的空对象。 |
| 删除整份 draft | `draft delete`：按相同的决定记录与引用校验删除当前子目，再隐藏对象。 |
| 改写／删除 Review 段落 | `review publish` 的 `set_blocks`／`remove_blocks`，先有真实 draft 修改依据。删除最后一段会保存空版本并自动隐藏成果。 |
| 删除整份 Review | `review delete`：凭真实 draft 原因删除全部当前段落，再隐藏成果。 |
| 移除原始材料 | `source delete`：从材料库隐藏来源并停止远端检查；已有引用和原始文件仍可读取，不代表撤回 draft 中的事实。 |
| 重新启用 | `draft restore`、`review restore`、`source restore`。来源原内容恢复展示；draft／Review 重新启用的是**当前空版本**，不会自动恢复旧业务内容。需要旧内容时读取旧版，再按正常因果流程写回。 |

`draft/review/source list --include-deleted` 查已删除身份，普通列表隐藏它们。`show` 仍能读取当前或历史版，并返回 `archived_at`。复用原类型/范围或来源前先重新启用，不能新建重复身份绕开历史。

## 输入与执行

六个命令均使用 `--project PROJECT_ID --request-id REQUEST_ID --input FILE --json`。用 Skill 辅助工具 `inspect_contract.py command draft.delete` 查询当前操作的准确契约，其他命令替换命令名。

所有输入都有 `api_version:"1"`、匹配的 `command` 和明确的 `reason`：

- 对象删除／重新启用：`object_id`、当前 `show` 返回的 `base_revision`。
- 来源删除／重新启用：`source_id`、以 `source show.head_snapshot_id` 为值的 `base_snapshot_id`。
- `draft delete`：可带 `decisions` 与 `instruction_source_version_id`。删除已采用决定必须同步记录新决定，`affected_items` 中操作 ID 使用内部 `op_id:"delete"`，保留真实用户指令与替代历史。D15 资源仍被交付/职责字段引用时，先纠正引用，或用 `draft apply` 同批删除相关子目，再隐藏空对象。失败不改对象。
- `review delete`：提供 `review prepare` 返回的 `read_basis`，以及覆盖所有被删段落的 `cause_change_ids`。整份成果删除指令先收录来源，再将其写入 draft `expression_guide`，指向 `*`、intent 为 `omit`，然后 prepare/delete；仅来源收录回执不构成原因。

来源删除示例（ID 替换成真实值）：

```json
{"api_version":"1","command":"source.delete","source_id":"ACTUAL_SOURCE_ID","base_snapshot_id":"ACTUAL_SNAPSHOT_ID","reason":"用户要求移出材料库"}
```

检查回执、列表可见性、历史版本和返回的 `affected_draft_items`／`affected_reviews` 或 `referenced_by`。按请求范围处理真实关联：draft 删除可用于移除依赖它的 Review 段落；只隐藏来源不撤回或改写事实。不能级联删除其他对象。即使旧轮次已不存在，仍可在真实原因和准确身份下删除相应 Review。

重新启用空 Review 后，`review prepare` 要显式选回实际 draft 条目；重新编写所需的新表达指令先存 draft，不能复用已消费的删除原因。原对象/段落身份保留，历史因果不重置。写入后刷新页面：当前列表隐藏删除记录，历史引用仍可追溯。没有永久清除命令。
