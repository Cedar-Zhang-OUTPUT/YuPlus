# 找案例前端与本地服务接口

已接入研究版本持久化、飞书 CLI 预览和临时缓存。沿用 [ADR-0001](../docs/adr/0001-case-finding-whiteboard-preview.md)，不创建 source/draft/review。远端内容由 Agent 使用飞书 Skill 写入，Yu+ 服务只读取。

## 入口与展示

- 当前项目导航：信息收集 → 整理与Review → 找案例。路由 `#/p/PROJECT/case-finding`。
- 标题右侧历史下拉：vN、创建于、更新于，时间按浏览器本地时区精确到秒。默认最新，当前页面内按项目保留选择。
- 中间展示选中版本的画板图片，支持比例缩放、拖动、键盘平移、适应窗口、展开对话框（Escape 退出）、打开飞书原内容。
- 底部横幅复用新建功能视觉语言，复制简短提示词，包含当前项目名称、ID、数据目录。明确表达开启新研究、新建版本、不覆盖或续改旧研究；复制本身不创建版本。
- 真实服务未提供记录时显示空态，不使用示例替代；明确 demo 服务提供 v1/v2 结构示意画板。demo 不访问飞书。

## 只读契约

`/api/view` 的可选 `case_findings` 数组：

```json
{
  "id": "case_version_id",
  "project_id": "project_id",
  "version": 2,
  "created_at": "2026-10-23T05:18:36Z",
  "updated_at": "2026-10-23T05:42:19Z",
  "board_url": "https://tenant.feishu.cn/docx/document_token#board_block_anchor",
  "document_url": "https://tenant.feishu.cn/docx/document_token",
  "preview": {
    "image_url": "/api/case-finding/images/cache_key",
    "fetched_at": "2026-10-23T05:42:22Z"
  }
}
```

`preview` 可缺失。记录属于找案例自身，可按项目归档，不代表与项目对象的业务关联。版本应指向各自的画板定位信息；不能让所有历史版本指向不断被覆盖的同一画板，再宣称保留了历史内容。版本更新时间与预览获取时间是两件事，刷新图片不改版本号或业务更新时间。

服务声明 `meta.case_finding_preview: true`，前端才启用：

`GET /api/case-finding/preview?project=PROJECT&version=VERSION`

返回 `{version_id, image_url, fetched_at}`。图片 URL 必须是本地 `/api/case-finding/images/KEY`，新图片使用新的 KEY 或内容标识 query，不能在缓存 URL 下静默替换内容。服务端负责验证项目与版本归属、只读飞书导出、并发合并、鉴权和缓存。401/403 映射认证/权限暂停，其他错误退避重试。前端不接收凭据、远程图片地址或任意文件路径。

当前前端参数：可见时每 60 秒刷新、30 秒请求超时、普通失败指数退避至最多 5 分钟。页面隐藏、画板不可见、切换版本或离开路由时取消请求及计时器；恢复可见时刷新。手动刷新复用同一流程。认证/权限错误停止周期请求，用户处理后可手动重试。

旧图片保留到新图片解码成功；版本切换隔离缓存并用请求代次屏蔽迟到结果。首次无图展示加载或错误状态，成功时间只随成功图片更新。版本列表由服务提供，刷新预览不会虚构新版本。

## 持久化与缓存

Schema 7 增加 `case_research`（项目、轮次、标题、文档/画板定位、元数据版本及时间）和幂等回执表。旧库迁移前备份。`research create` 预留新轮次，`research update` 首次关联或登记同轮成功修改，`research list/show/preview` 读取及验证。定位首次绑定后不替换；不同轮次不得共享同一 board token。

缓存位于 macOS `~/Library/Caches/yuplus/case-previews/<数据目录散列>`（其他平台 `~/.cache/yuplus/...`），不进入业务库或备份。接受最大 20 MiB 的 PNG/JPEG、验证图片结构/尺寸、内容散列命名，前端解码成功后显示。每个数据目录最多 32 张 / 128 MiB，7 天过期，在成功刷新时清理；失去缓存可重新获取。

服务跨进程串行化导出，重叠请求复用成功结果（2 秒合并窗），飞书命令超时 24 秒。只导出请求的已关联画板，不遍历案例库。HEAD 不触发远端调用。项目归档后拒绝图片访问及继续导出。手动刷新不会更新轮次的业务时间；飞书直接编辑的修改时间不伪装成本地保存时间。

完整链路验证见 `docs/testing/case-research-integration.md`。

## 已确认的工作流与链接行为

底部提示词启动新研究，首次 v1，之后 v2…；同轮补图、改说明和用户在飞书直接编辑均沿用该版本；中断重试不新增版本。独立版本保存独立画板定位。

刷新按钮左侧显示「打开飞书画板 ↗」，优先使用所选版本的 `board_url`（由实际飞书返回/核验的直达链接，保留锚点），兼容 `document_url`。使用新标签页及 `noopener noreferrer`；缺少有效地址时入口禁用，不编造示例跳转。切换版本同步切换链接。demo 只有示例图，不声称能打开真实画板。

Agent 工作流见 [case-research.md](../skills/yuplus/references/case-research.md)；案例素材与详细索引存飞书，Yu+ 仅登记成果元数据，单次偏好不形成长期档案。
