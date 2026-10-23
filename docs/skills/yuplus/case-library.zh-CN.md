# 工作空间案例库源

新增、查找案例或移除案例库时读取。案例库是所有项目共用的飞书共享文件夹，不属于项目或 draft/review 对象。**Yu+ 只保存名称、链接和登记元数据，内容始终留在飞书。** 不把文件、正文、摘录、目录清单或检索索引存入 Yu+，不执行文件夹拉取、同步或后台扫描。

## 登记与使用

- 登记：通过已安装的 `lark-drive` 获取真实标题，再执行 `library add`。无权限时说明问题，请用户提供可访问链接或名称；不能编造读取成功。相同链接复用已有登记。
- 每次需要案例时：`library list` → 选择相关的有效登记 → `library show` → 使用**飞书 CLI**在该共享文件夹中查找、读取。此时按需阅读 `lark-drive` 的目录列取／搜索指引，已读则复用。关键词查找优先按已安装指引使用 `lark-cli drive +search --query 关键词 --folder-tokens 文件夹TOKEN --as user --format json`；目录枚举用于浏览，不是搜索的必经步骤。限定该文件夹及相关子文件夹，处理分页，并核对搜索结果归属；选中内容按类型使用对应飞书 Skill。Yu+ 不提供本地案例内容搜索。
- 向用户展示案例真实标题、飞书原链接及相关理由。可讨论面向当前项目的创意，但不把案例材料归档到 Yu+；不能把登记链接或部分搜索说成已完成内容收集。读取工具若需要临时文件，应放在 Yu+ 数据／备份目录之外，不形成持久案例缓存。

## CLI

使用已核验的工作空间 `--data-dir`，不传 `--project`。页面只复制 Prompt；写入成功后核对回执、刷新 `#/libraries`。

```sh
yu library list --json
yu library show --library LIBRARY_ID --json
yu library add --request-id UNIQUE_ID --input request.json --json
```

新增输入：
```json
{"api_version":"1","command":"library.add","name":"文件夹真实名称","url":"https://tenant.feishu.cn/drive/folder/TOKEN"}
```

修改用 `library update`，同样的信封内传 `library_id`、当前 `base_version`、`name` 和 `url`。回执含 `id`（library_id）、`version`、名称、链接和时间；`meta.library_policy` 明确按需从飞书查询、仅移除本地登记。写操作使用新 request ID；相同请求重试时复用原 ID。

## 移除与恢复

用户删除案例库，表示**只移除 Yu+ 登记**，不删除或改变飞书文件夹。先 `library show` 核对 ID 并取得当前版本，不调用飞书删除接口。

```sh
yu library delete --request-id UNIQUE_ID --input request.json --json
```
```json
{"api_version":"1","command":"library.delete","library_id":"LIBRARY_ID","base_version":1}
```

替换为真实 ID 和版本。软删除后页面及普通列表隐藏该库，登记元数据与操作回执保留。用 `library list` 核验。恢复时先 `library list --include-deleted` 找到记录并读取当前版本，再执行 `library restore`，使用匹配的 command 和相同的 `library_id`、`base_version` 字段。恢复只恢复链接登记，不操作飞书或下载内容。
