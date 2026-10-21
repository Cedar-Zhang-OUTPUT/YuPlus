# Yu+ 数据与 CLI 契约 v0.1

本目录是设计产物，不是数据库安装包或 CLI 实现。

- schema.sql：13 张表及 SQLite 约束。
- cli-input.schema.json：四个核心命令的输入，包括各类 draft 的数据字段。
- cli-output.schema.json：输出信封；各命令 data 内容见主文档和 examples，尚未逐一写成机器 Schema。
- object-types.json：来自已确认对象关系的 24 类属性目录，供后续 Skill、CLI、展示层共用。
- examples：说明性请求、结果和冲突分支，不是真实执行日志。
- verify_contracts.py：在内存 SQLite 中验证 DDL，并检查 JSON Schema 和示例。

验证需要支持 STRICT/JSON 的 SQLite，正式产品沿用架构文档指定的版本下限。验证 Python 环境另行安装 requirements-validation.txt 后运行：

```sh
python verify_contracts.py
```

必须包含 jsonschema 的 format 依赖，否则日期格式检查可能被跳过；验证程序包含非法日期用例以检测该问题。当前产品运行时使用 Python/jsonschema；此脚本只覆盖契约层，完整服务验证见仓库 tests。

当前 JSON 契约与运行时同步，保留 v0.1 路径以兼容既有引用。schema.sql 是 schema 1 基线；应用还会执行 monitor-schema.sql（schema 2）及 src/yuplus/migrations.py 的开放性问题迁移（schema 3）。请通过 CLI 初始化/升级，不直接把该基线 SQL 当成最新版完整数据库。
