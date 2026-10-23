# 全局头像

更改左上角 Logo/头像时使用当前 Yu+ 数据目录，不传 `--project`。无需读取或改动项目、来源、draft、review。

1. 使用用户附上的图片；未附图就提醒上传。复制提示词不等于已上传图片。
2. 保留原图，在临时副本上按比例缩小到最长边 **256 px**，导出静态、非交错、8-bit **PNG**，保留原有透明背景。不擅自生成新图或裁切。macOS 可运行 `sips -s format png -Z 256 原图 --out 临时文件.png`；路径正确加引号，输出使用新的临时路径。其他平台使用可用的图像转换工具。CLI 限制为 512×512、256 KiB，超限则继续缩小。
3. `yu logo show --data-dir 数据目录 --json` 读取 `data.version`（初始为 0）。生成 JSON 文件并写入：

```sh
yu logo set --data-dir 数据目录 --request-id req_logo_unique --input /tmp/logo-request.json --json
```

```json
{"api_version":"1","command":"logo.set","base_version":0,"local_path":"/绝对路径/压缩后的图片.png"}
```

版本和路径用实际值。Yu+ 校验图片、去除非必要 PNG 元数据、压缩后存入 SQLite，备份恢复会包含头像。验证完成后可清理临时副本，不删除用户原图。

4. 查询 `logo show` 核实，刷新现有本地页面并查看头像，无需重启。写入成功后才能报告完成。版本冲突时重读；仅重试同一写入时复用 request-id。

用户明确要求恢复默认 Logo 时，使用 `logo reset` 和相同参数，JSON 为 `{"api_version":"1","command":"logo.reset","base_version":当前版本}`。重置保留递增版本，不影响项目及材料。
