/* ═══════════════════════════════════════════════════════════════════════════
   Yu+ 示例数据 · 演示用，非真实客户材料
   ---------------------------------------------------------------------------
   仅供前端调试的视图模型，不是 CLI 输入或数据库 schema：
     projects · changes · sources · source_versions · blobs · source_files
     objects · object_revisions · revision_sources · revision_dependencies
     decisions · review_checks · exports
   draft payload  = { title, items:[{item_id, data, epistemic_kind}] }
   review payload = { title, blocks:[{block_id, markdown}] }
   ID 稳定、版本追加不可变；无真实飞书/文件访问。
   ═══════════════════════════════════════════════════════════════════════════ */
import { DESIGN_FIXTURES } from "./design-fixtures.js";

const DATA = (() => {
  "use strict";

  const NOW = "2026-10-16T06:30:00Z";

  /* ── 便捷构造 ──────────────────────────────────────────────────────────── */

  // 来源引用：某个 draft 条目采用了哪一版来源快照、引到哪一段
  const ref = (evidence_id, source_version_id, evidence_kind, extra) =>
    Object.assign({ evidence_id, source_version_id, evidence_kind, locator: {} }, extra || {});

  // 依赖：消费方条目依赖生产方对象的具体条目与版本
  const dep = (dependency_id, producer_object_id, producer_revision_id, producer_item_id, kind, fingerprint) =>
    ({ dependency_id, producer_object_id, producer_revision_id, producer_item_id, dependency_kind: kind || "fact", fingerprint });

  const dt = (t) => `2026-10-${t}`;

  /* ══════════════════════ projects ══════════════════════════════════════ */

  const projects = [
    {
      id: "prj_city", name: "城市记忆展厅", lifecycle: "active", working_scene: "review",
      client_summary: "市文旅局 · 2027 春季开馆 · 常设展首期策展",
      created_at: dt("01T02:10:00Z"), updated_at: dt("13T09:12:40Z"), archived_at: null,
    },
    {
      id: "prj_yudev", name: "YU+ Dev", lifecycle: "active", working_scene: "draft",
      client_summary: "内部产品 · 对象语义与前端验证",
      created_at: dt("08T06:00:00Z"), updated_at: dt("12T14:31:00Z"), archived_at: null,
    },
    {
      id: "prj_river", name: "沿江夜游提案", lifecycle: "active", working_scene: "draft",
      client_summary: "旅投集团 · 前期咨询 · 尚未收录材料",
      created_at: dt("12T11:05:00Z"), updated_at: dt("12T11:05:00Z"), archived_at: null,
    },
    {
      id: "prj_lake", name: "湖畔书展", lifecycle: "archived", working_scene: "review",
      client_summary: "出版社联合体 · 2026 秋季 · 已结项并归档",
      created_at: "2026-06-02T03:00:00Z", updated_at: "2026-09-04T08:00:00Z", archived_at: "2026-09-04T08:00:00Z",
    },
    // 同名项目：名称相同但身份不同，用于检验项目区分能力
    {
      id: "prj_city_2", name: "城市记忆展厅", lifecycle: "active", working_scene: "draft",
      client_summary: "同名续标 · 二期展陈（与首期不同项目）",
      created_at: dt("10T07:40:00Z"), updated_at: dt("11T05:20:00Z"), archived_at: null,
    },
  ];

  // 项目活动摘要（用于项目列表的“最近已保存变更”），全部来自真实 change 记录
  const project_activity = {
    prj_city: { change_id: "chg_031", summary: "更新交付细节：本轮交付由「成片」改为「概念脚本」", at: dt("13T09:12:40Z") },
    prj_yudev: { change_id: "chg_104", summary: "更新 D18 交付细节，并新增 D22 风险点", at: dt("12T14:31:00Z") },
    prj_river: null,
    prj_lake: { change_id: "chg_060", summary: "发布 R01 主策 Debrief 第 3 版", at: "2026-09-04T08:00:00Z" },
    prj_city_2: { change_id: "chg_007", summary: "新增 D11 合作类型：竞标", at: dt("11T05:20:00Z") },
  };

  /* ══════════════════════ sources · source_versions · files ════════════ */

  const sources = [
    {
      id: "src_brief", project_id: "prj_city", provider: "feishu", resource_type: "docx",
      provider_key: "docx_city_brief_v3", canonical_url: "https://example.feishu.cn/docx/docx_city_brief_v3",
      cached_title: "城市记忆展厅｜项目需求与预算说明（V3）",
      latest_snapshot_id: "sv_brief_2", last_checked_at: dt("13T08:02:00Z"),
      remote_observation: {
        observed_revision: "rev_2026_10_13_a", method: "docx_revision",
        checked_at: dt("13T08:02:00Z"), conclusion: "changed",
        detail: "远端 revision 由 rev_2026_10_09_c 变为 rev_2026_10_13_a",
      },
      check_error: null, created_at: dt("02T03:40:00Z"), archived_at: null,
    },
    {
      id: "src_meeting", project_id: "prj_city", provider: "feishu", resource_type: "minutes",
      provider_key: "minute_kickoff_1009", canonical_url: "https://example.feishu.cn/minutes/minute_kickoff_1009",
      cached_title: "城市记忆展厅｜10 月 9 日开工会纪要",
      latest_snapshot_id: "sv_meeting_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("09T10:20:00Z"), archived_at: null,
    },
    {
      id: "src_site_plan", project_id: "prj_city", provider: "local", resource_type: "pdf",
      provider_key: "sha256:site_plan_a3f8", canonical_url: null,
      cached_title: "场馆平面图_A区_20260915.pdf",
      latest_snapshot_id: "sv_site_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("05T02:00:00Z"), archived_at: null,
    },
    {
      id: "src_site_photos", project_id: "prj_city", provider: "local", resource_type: "folder",
      provider_key: "sha256:site_photos_9c12", canonical_url: null,
      cached_title: "现场勘察照片（9 张）",
      latest_snapshot_id: "sv_photos_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("06T01:30:00Z"), archived_at: null,
    },
    {
      id: "src_brand", project_id: "prj_city", provider: "feishu", resource_type: "bitable",
      provider_key: "base_brand_assets_v1", canonical_url: "https://example.feishu.cn/base/base_brand_assets_v1",
      cached_title: "文旅局品牌资产与视觉规范清单",
      latest_snapshot_id: "sv_brand_1", last_checked_at: dt("13T08:02:00Z"),
      remote_observation: {
        observed_revision: "rev_2026_10_13_a", method: "bitable_revision",
        checked_at: dt("13T08:02:00Z"), conclusion: "unchanged",
        detail: "远端 revision 未变化",
      },
      check_error: null, created_at: dt("04T06:10:00Z"), archived_at: null,
    },
    // 口述：用户决定把预算按 60 万推进
    {
      id: "src_oral_budget", project_id: "prj_city", provider: "oral", resource_type: "statement",
      provider_key: "oral_20261011_budget", canonical_url: null,
      cached_title: "主策口述：本轮按 60 万推进（10 月 11 日）",
      latest_snapshot_id: "sv_oral_budget_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("11T07:15:00Z"), archived_at: null,
    },
    // 口述：表达要求
    {
      id: "src_oral_style", project_id: "prj_city", provider: "oral", resource_type: "statement",
      provider_key: "oral_20261012_style", canonical_url: null,
      cached_title: "主策口述：主策 Debrief 预算段简明（10 月 12 日）",
      latest_snapshot_id: "sv_oral_style_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("12T03:05:00Z"), archived_at: null,
    },
    // 口述：交付从成片改为概念脚本
    {
      id: "src_oral_scope", project_id: "prj_city", provider: "oral", resource_type: "statement",
      provider_key: "oral_20261013_scope", canonical_url: null,
      cached_title: "主策口述：本轮只交概念脚本（10 月 13 日）",
      latest_snapshot_id: "sv_oral_scope_1", last_checked_at: null,
      remote_observation: null, check_error: null, created_at: dt("13T09:05:00Z"), archived_at: null,
    },
    // 仅保存裸链接、元信息尚未取得的例子
    {
      id: "src_tender_raw", project_id: "prj_city", provider: "web", resource_type: "link",
      provider_key: "web_tender_portal_9201", canonical_url: "https://example.gov.cn/tender/9201?from=share",
      cached_title: "招标公告链接（尚未取得标题）",
      latest_snapshot_id: null, last_checked_at: null,
      remote_observation: null,
      check_error: { code: "FEISHU_UNAVAILABLE", message: "首次读取标题时网络不可用，已保留地址", at: dt("03T05:00:00Z") },
      created_at: dt("03T05:00:00Z"), archived_at: null,
    },
    // 外部引用文件，当前不可用
    {
      id: "src_old_deck", project_id: "prj_city", provider: "local", resource_type: "pptx",
      provider_key: "external:/Volumes/Archive/city_deck_2024.pptx", canonical_url: null,
      cached_title: "城市记忆展厅_概念提案_2024.pptx",
      latest_snapshot_id: "sv_deck_1", last_checked_at: dt("12T02:00:00Z"),
      remote_observation: null,
      check_error: { code: "FILE_NOT_FOUND", message: "登记时保存的外部路径当前不可访问", at: dt("12T02:00:00Z") },
      created_at: dt("03T06:00:00Z"), archived_at: null,
    },
  ];

  const source_versions = [
    {
      id: "sv_brief_1", source_id: "src_brief", version: 1, provider_revision: "rev_2026_10_09_c",
      capture_scope: { mode: "full" }, title_at_capture: "城市记忆展厅｜项目需求与预算说明（V3）",
      captured_at: dt("02T03:38:00Z"), recorded_at: dt("02T03:40:00Z"), change_id: "chg_001",
      body_format: "markdown",
      body_text:
        "## 一、项目背景\n\n市文旅局拟在滨江旧仓改造常设展厅，2027 年春季开馆。首期要求以「城市记忆」为主线，覆盖三个历史断面。\n\n## 二、交付要求\n\n- 首期需提交 **成片**：8 分钟主影片 1 支，供开馆日循环播放。\n- 需同步提交 3 面展墙的图文排版稿。\n\n## 三、预算\n\n本轮项目总预算 **100 万元**（人民币），含制作、版权与设备。\n\n## 四、时间\n\n- 2026-12-20 前提交创意方向\n- 2027-02-10 前完成成片交付\n",
      assets: [{ asset_id: "a_body", role: "body", display_name: "城市记忆展厅｜项目需求与预算说明（V3）.md", mime_type: "text/markdown", size_bytes: 6140, availability: "local_copy" }],
    },
    {
      id: "sv_brief_2", source_id: "src_brief", version: 2, provider_revision: "rev_2026_10_13_a",
      capture_scope: { mode: "full" }, title_at_capture: "城市记忆展厅｜项目需求与预算说明（V3）",
      captured_at: dt("13T08:01:00Z"), recorded_at: dt("13T08:02:00Z"), change_id: "chg_029",
      body_format: "markdown",
      body_text:
        "## 一、项目背景\n\n市文旅局拟在滨江旧仓改造常设展厅，2027 年春季开馆。首期要求以「城市记忆」为主线，覆盖三个历史断面。\n\n## 二、交付要求\n\n- 首期需提交 **成片**：8 分钟主影片 1 支，供开馆日循环播放。\n- 需同步提交 3 面展墙的图文排版稿。\n\n## 三、预算\n\n本轮项目总预算 **100 万元**（人民币），含制作、版权与设备。\n\n## 四、时间\n\n- 2026-12-20 前提交创意方向\n- 2027-02-10 前完成成片交付\n\n## 五、补充（10 月 13 日）\n\n- 增加「口述史采集」素材包要求：不少于 12 位受访者的音频与文字整理。\n",
      assets: [{ asset_id: "a_body", role: "body", display_name: "城市记忆展厅｜项目需求与预算说明（V3）.md", mime_type: "text/markdown", size_bytes: 6790, availability: "local_copy" }],
    },
    {
      id: "sv_meeting_1", source_id: "src_meeting", version: 1, provider_revision: "minute_rev_a",
      capture_scope: { mode: "selection", note: "议题 2、4 的转写段落" },
      title_at_capture: "城市记忆展厅｜10 月 9 日开工会纪要",
      captured_at: dt("09T10:18:00Z"), recorded_at: dt("09T10:20:00Z"), change_id: "chg_005",
      body_format: "text",
      body_text:
        "【议题 2｜交付形态】\n文旅局李处：开馆日需要一支能循环播放的主影片，这个别砍。时长控制在 8 分钟左右。\n\n【议题 4｜受众】\n李处：现场主要是亲子家庭和研学团，本地市民占多数；线上的话我们自己的公众号会推一次。\n\n【议题 5｜报批】\n最终验收由李处签字；预算追加需要局办会通过。\n",
      assets: [{ asset_id: "a_transcript", role: "transcript", display_name: "开工会转写_节选.txt", mime_type: "text/plain", size_bytes: 2210, availability: "local_copy" }],
    },
    {
      id: "sv_site_1", source_id: "src_site_plan", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "场馆平面图_A区_20260915.pdf",
      captured_at: dt("05T01:58:00Z"), recorded_at: dt("05T02:00:00Z"), change_id: "chg_003",
      body_format: null, body_text: null,
      assets: [
        { asset_id: "a_pdf", role: "original", display_name: "场馆平面图_A区_20260915.pdf", mime_type: "application/pdf", size_bytes: 3841022, availability: "local_copy", pages: 4 },
      ],
    },
    {
      id: "sv_photos_1", source_id: "src_site_photos", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "现场勘察照片（9 张）",
      captured_at: dt("06T01:28:00Z"), recorded_at: dt("06T01:30:00Z"), change_id: "chg_004",
      body_format: null, body_text: null,
      assets: [
        { asset_id: "a_01", role: "attachment", display_name: "A区_北向_01.jpg", mime_type: "image/jpeg", size_bytes: 2814000, availability: "local_copy", caption: "北向通高约 7.2m，保留原有桁架" },
        { asset_id: "a_02", role: "attachment", display_name: "A区_西墙_02.jpg", mime_type: "image/jpeg", size_bytes: 2651000, availability: "local_copy", caption: "西墙砖面，局部渗水痕迹" },
        { asset_id: "a_03", role: "attachment", display_name: "A区_入口_03.jpg", mime_type: "image/jpeg", size_bytes: 3012000, availability: "local_copy", caption: "入口层高受限，约 3.1m" },
        { asset_id: "a_04", role: "attachment", display_name: "B区_天窗_04.jpg", mime_type: "image/jpeg", size_bytes: 2440000, availability: "local_copy", caption: "天窗遮光需另行处理" },
      ],
    },
    {
      id: "sv_brand_1", source_id: "src_brand", version: 1, provider_revision: "rev_2026_10_13_a",
      capture_scope: { mode: "full" }, title_at_capture: "文旅局品牌资产与视觉规范清单",
      captured_at: dt("04T06:08:00Z"), recorded_at: dt("04T06:10:00Z"), change_id: "chg_002",
      body_format: "markdown",
      body_text:
        "| 资产 | 类型 | 使用条件 |\n|---|---|---|\n| 局徽（横版） | SVG | 开馆物料可用，禁止改色 |\n| 主视觉「江线」 | AI | 仅限本项目，需署名 |\n| 历史影像档案 | 授权图库 | 按张计费，单张上限 2000 元 |\n",
      assets: [
        { asset_id: "a_sheet", role: "body", display_name: "品牌资产清单.md", mime_type: "text/markdown", size_bytes: 1180, availability: "local_copy" },
        { asset_id: "a_logo", role: "preview", display_name: "局徽_横版.svg", mime_type: "image/svg+xml", size_bytes: 22400, availability: "local_copy" },
      ],
    },
    {
      id: "sv_oral_budget_1", source_id: "src_oral_budget", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "主策口述：本轮按 60 万推进（10 月 11 日）",
      captured_at: dt("11T07:15:00Z"), recorded_at: dt("11T07:15:00Z"), change_id: "chg_020",
      body_format: "text",
      body_text: "客户那边 100 万的数是含了他们自己的设备采购。我们这边本轮实际按 60 万推进，设备那块走他们的采购流程。别再按 100 万排方案了。",
      assets: [{ asset_id: "a_oral", role: "transcript", display_name: "主策口述_预算_1011.txt", mime_type: "text/plain", size_bytes: 186, availability: "local_copy" }],
    },
    {
      id: "sv_oral_style_1", source_id: "src_oral_style", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "主策口述：主策 Debrief 预算段简明（10 月 12 日）",
      captured_at: dt("12T03:05:00Z"), recorded_at: dt("12T03:05:00Z"), change_id: "chg_024",
      body_format: "text",
      body_text: "Debrief 里预算那一块写得太啰嗦了，客户只想知道我们按多少做。精简一点，别把两个数都铺开讲。",
      assets: [{ asset_id: "a_oral", role: "transcript", display_name: "主策口述_表达_1012.txt", mime_type: "text/plain", size_bytes: 152, availability: "local_copy" }],
    },
    {
      id: "sv_oral_scope_1", source_id: "src_oral_scope", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "主策口述：本轮只交概念脚本（10 月 13 日）",
      captured_at: dt("13T09:05:00Z"), recorded_at: dt("13T09:05:00Z"), change_id: "chg_030",
      body_format: "text",
      body_text: "跟创作者那边确认一下，这轮不要要求他们做成片，只要概念脚本就行。成片等下一轮再说。",
      assets: [{ asset_id: "a_oral", role: "transcript", display_name: "主策口述_交付_1013.txt", mime_type: "text/plain", size_bytes: 168, availability: "local_copy" }],
    },
    {
      id: "sv_deck_1", source_id: "src_old_deck", version: 1, provider_revision: null,
      capture_scope: { mode: "full" }, title_at_capture: "城市记忆展厅_概念提案_2024.pptx",
      captured_at: dt("03T05:58:00Z"), recorded_at: dt("03T06:00:00Z"), change_id: "chg_006",
      body_format: null, body_text: null,
      assets: [
        { asset_id: "a_pptx", role: "original", display_name: "城市记忆展厅_概念提案_2024.pptx", mime_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation", size_bytes: 15420000, availability: "external_missing", external_path: "/Volumes/Archive/city_deck_2024.pptx", external_sha256: "b7c1e0d5a4f34c2a9e8b7d6c5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f60", external_size_bytes: 15420000 },
      ],
    },
  ];

  const captures = [
    { id: "cap_1", minute: "05:12", speaker: "李处（文旅局）", text: "开馆日需要一支能循环播放的主影片，这个别砍。时长控制在 8 分钟左右。", source_version_id: "sv_meeting_1" },
    { id: "cap_2", minute: "11:40", speaker: "李处（文旅局）", text: "现场主要是亲子家庭和研学团，本地市民占多数。", source_version_id: "sv_meeting_1" },
    { id: "cap_3", minute: "23:05", speaker: "李处（文旅局）", text: "最终验收由我签字；预算追加需要局办会通过。", source_version_id: "sv_meeting_1" },
  ];

  /* ══════════════════════ objects · object_revisions ════════════════════ */

  const objects = [
    { id: "obj_bd", project_id: "prj_city", layer: "draft", type_key: "bd_context", scope_key: "project", current_revision_id: "rev_bd_2", created_at: dt("02T04:00:00Z") },
    { id: "obj_brief", project_id: "prj_city", layer: "draft", type_key: "client_brief", scope_key: "project", current_revision_id: "rev_brief_2", created_at: dt("02T04:05:00Z") },
    { id: "obj_tender", project_id: "prj_city", layer: "draft", type_key: "tender_documents", scope_key: "project", current_revision_id: null, created_at: dt("03T05:20:00Z") },
    { id: "obj_venue", project_id: "prj_city", layer: "draft", type_key: "venue", scope_key: "project", current_revision_id: "rev_venue_1", created_at: dt("06T02:00:00Z") },
    { id: "obj_brand", project_id: "prj_city", layer: "draft", type_key: "brand_assets", scope_key: "project", current_revision_id: "rev_brand_1", created_at: dt("04T07:00:00Z") },
    { id: "obj_audience", project_id: "prj_city", layer: "draft", type_key: "audience", scope_key: "project", current_revision_id: "rev_audience_1", created_at: dt("09T11:00:00Z") },
    { id: "obj_budget", project_id: "prj_city", layer: "draft", type_key: "budget_range", scope_key: "project", current_revision_id: "rev_budget_2", created_at: dt("02T04:10:00Z") },
    { id: "obj_alloc", project_id: "prj_city", layer: "draft", type_key: "budget_allocation", scope_key: "project", current_revision_id: "rev_alloc_2", created_at: dt("08T03:00:00Z") },
    { id: "obj_timeline", project_id: "prj_city", layer: "draft", type_key: "milestones", scope_key: "project", current_revision_id: "rev_timeline_1", created_at: dt("09T11:20:00Z") },
    { id: "obj_clientdec", project_id: "prj_city", layer: "draft", type_key: "client_decisions", scope_key: "project", current_revision_id: "rev_clientdec_1", created_at: dt("09T11:40:00Z") },
    { id: "obj_coop", project_id: "prj_city", layer: "draft", type_key: "cooperation_type", scope_key: "project", current_revision_id: "rev_coop_1", created_at: dt("02T04:20:00Z") },
    { id: "obj_competitor", project_id: "prj_city", layer: "draft", type_key: "competitor_analysis", scope_key: "project", current_revision_id: null, created_at: dt("05T08:00:00Z") },
    { id: "obj_history", project_id: "prj_city", layer: "draft", type_key: "client_history", scope_key: "project", current_revision_id: null, created_at: dt("05T08:10:00Z") },
    { id: "obj_meetings", project_id: "prj_city", layer: "draft", type_key: "client_meetings", scope_key: "project", current_revision_id: "rev_meetings_1", created_at: dt("09T12:00:00Z") },
    { id: "obj_qa", project_id: "prj_city", layer: "draft", type_key: "qa", scope_key: "project", current_revision_id: "rev_qa_1", created_at: dt("10T02:00:00Z") },
    { id: "obj_assess", project_id: "prj_city", layer: "draft", type_key: "project_assessment", scope_key: "project", current_revision_id: null, created_at: dt("07T02:00:00Z") },
    { id: "obj_strategy", project_id: "prj_city", layer: "draft", type_key: "lead_strategy", scope_key: "project", current_revision_id: "rev_strategy_1", created_at: dt("10T06:00:00Z") },
    { id: "obj_deliv", project_id: "prj_city", layer: "draft", type_key: "deliverables", scope_key: "project", current_revision_id: "rev_deliv_2", created_at: dt("02T04:30:00Z") },
    { id: "obj_resources", project_id: "prj_city", layer: "draft", type_key: "resources", scope_key: "project", current_revision_id: "rev_resources_1", created_at: dt("10T07:00:00Z") },
    { id: "obj_resp", project_id: "prj_city", layer: "draft", type_key: "responsibilities", scope_key: "project", current_revision_id: "rev_resp_1", created_at: dt("09T12:30:00Z") },
    { id: "obj_rating", project_id: "prj_city", layer: "draft", type_key: "project_rating", scope_key: "project", current_revision_id: null, created_at: dt("07T02:10:00Z") },
    { id: "obj_risks", project_id: "prj_city", layer: "draft", type_key: "risks", scope_key: "project", current_revision_id: "rev_risks_1", created_at: dt("10T07:30:00Z") },
    { id: "obj_decision", project_id: "prj_city", layer: "draft", type_key: "assessment_decision", scope_key: "project", current_revision_id: null, created_at: dt("07T02:20:00Z") },

    // 内部类型：成果编写要求（不是第 24 类业务对象）
    { id: "obj_guide_r01", project_id: "prj_city", layer: "draft", type_key: "expression_guide", scope_key: "review:obj_r01", current_revision_id: "rev_guide_1", created_at: dt("12T03:10:00Z") },

    // YU+ Dev 项目：用于检验项目隔离
    { id: "obj_yd_deliv", project_id: "prj_yudev", layer: "draft", type_key: "deliverables", scope_key: "project", current_revision_id: "rev_yd_deliv_1", created_at: dt("12T14:31:00Z") },
    { id: "obj_yd_risk", project_id: "prj_yudev", layer: "draft", type_key: "risks", scope_key: "project", current_revision_id: "rev_yd_risk_1", created_at: dt("12T14:31:00Z") },

    // review 成果（R05 不在其中，直接读 D15）
    { id: "obj_r01", project_id: "prj_city", layer: "review", type_key: "debrief", scope_key: "project", current_revision_id: "rev_r01_2", created_at: dt("09T14:00:00Z") },
    { id: "obj_r02", project_id: "prj_city", layer: "review", type_key: "advancement", scope_key: "project", current_revision_id: "rev_r02_1", created_at: dt("09T14:10:00Z") },
    { id: "obj_r03", project_id: "prj_city", layer: "review", type_key: "creative_review", scope_key: "project", current_revision_id: "rev_r03_1", created_at: dt("11T03:00:00Z") },
    { id: "obj_r04", project_id: "prj_city", layer: "review", type_key: "creator_brief", scope_key: "creator:res_zhou:round:r1", current_revision_id: "rev_r04_1", created_at: dt("11T04:00:00Z") },
    { id: "obj_r04b", project_id: "prj_city", layer: "review", type_key: "creator_brief", scope_key: "creator:res_lin:round:r1", current_revision_id: "rev_r04b_1", created_at: dt("11T04:20:00Z") },
  ];

  // 条目构造：data 为该对象的业务字段
  const item = (item_id, epistemic_kind, data, source_refs, dependencies) =>
    ({ item_id, data, epistemic_kind, source_refs: source_refs || [], dependencies: dependencies || [] });

  const object_revisions = [
    /* ── D01 BD 同步信息 ─────────────────────────────────────────────── */
    {
      id: "rev_bd_1", object_id: "obj_bd", version: 1, created_at: dt("02T04:00:00Z"), change_id: "chg_001",
      payload: {
        title: "BD 同步信息",
        item_order: ["bd_background"],
        items: [item("bd_background", "source_statement", {
          topic: "项目背景",
          text: "市文旅局 2026 年 9 月启动滨江旧仓改造，拟设「城市记忆」常设展厅，2027 年春季开馆。首期由我方承接创意与制作。",
        }, [ref("ev_bd_1", "sv_brief_1", "quote")])],
      },
    },
    {
      id: "rev_bd_2", object_id: "obj_bd", version: 2, created_at: dt("09T12:40:00Z"), change_id: "chg_008",
      payload: {
        title: "BD 同步信息",
        item_order: ["bd_background", "bd_why_now", "bd_goal", "bd_criteria", "bd_preference"],
        items: [
          item("bd_background", "source_statement", {
            topic: "项目背景",
            text: "市文旅局 2026 年 9 月启动滨江旧仓改造，拟设「城市记忆」常设展厅，2027 年春季开馆。首期由我方承接创意与制作。",
          }, [ref("ev_bd_1", "sv_brief_1", "quote")]),
          item("bd_why_now", "reported", {
            topic: "客户为何现在做",
            text: "BD 转述：局里今年有文旅专项拨款窗口，年底前必须完成立项采购，否则额度收回。",
          }, [ref("ev_bd_2", "sv_brief_1", "reported")]),
          item("bd_goal", "source_statement", {
            topic: "目标",
            text: "在开馆日交付可循环播放的主影片与展墙图文，建立展厅的首期叙事框架。",
          }, [ref("ev_bd_3", "sv_brief_1", "quote")]),
          item("bd_criteria", "user_supplement", {
            topic: "决策标准",
            text: "客户以「历史表述是否准确」和「本地市民能否共鸣」为首要标准，预算控制次之。",
          }, [ref("ev_bd_4", "sv_meeting_1", "reported")]),
          item("bd_preference", "hypothesis", {
            topic: "偏好（待确认）",
            text: "客户对 2024 年同类展陈的「沉浸式声场」处理表现出兴趣，但未明确要求本轮采用。",
          }, [ref("ev_bd_5", "sv_deck_1", "supports")]),
        ],
      },
    },

    /* ── D02 客户原始 Brief ──────────────────────────────────────────── */
    {
      id: "rev_brief_1", object_id: "obj_brief", version: 1, created_at: dt("02T04:05:00Z"), change_id: "chg_001",
      payload: {
        title: "客户原始 Brief",
        item_order: ["req_film", "req_wall"],
        items: [
          item("req_film", "source_statement", { requirement: "首期提交 8 分钟主影片 1 支，开馆日循环播放", original_position: "第二节 交付要求" }, [ref("ev_bf_1", "sv_brief_1", "quote", { locator: { heading: "二、交付要求", quote: "首期需提交 **成片**：8 分钟主影片 1 支" } })]),
          item("req_wall", "source_statement", { requirement: "提交 3 面展墙的图文排版稿", original_position: "第二节 交付要求" }, [ref("ev_bf_2", "sv_brief_1", "quote", { locator: { heading: "二、交付要求" } })]),
        ],
      },
    },
    {
      id: "rev_brief_2", object_id: "obj_brief", version: 2, created_at: dt("13T08:20:00Z"), change_id: "chg_029",
      payload: {
        title: "客户原始 Brief",
        item_order: ["req_film", "req_wall", "req_oral", "correction_1"],
        items: [
          item("req_film", "source_statement", { requirement: "首期提交 8 分钟主影片 1 支，开馆日循环播放", original_position: "第二节 交付要求" }, [ref("ev_bf_1", "sv_brief_1", "quote", { locator: { heading: "二、交付要求", quote: "首期需提交 **成片**：8 分钟主影片 1 支" } })]),
          item("req_wall", "source_statement", { requirement: "提交 3 面展墙的图文排版稿", original_position: "第二节 交付要求" }, [ref("ev_bf_2", "sv_brief_1", "quote", { locator: { heading: "二、交付要求" } })]),
          item("req_oral", "source_statement", { requirement: "新增：口述史采集素材包，不少于 12 位受访者的音频与文字整理", original_position: "第五节 补充（10 月 13 日）" }, [ref("ev_bf_3", "sv_brief_2", "quote", { locator: { heading: "五、补充（10 月 13 日）" } })]),
          item("correction_1", "user_supplement", { requirement: "口径纠正：需求文档写「成片」，但本轮实际只做概念脚本，成片顺延至下一轮", note: "这是主策的补充说明，不是客户原文" }, [ref("ev_bf_4", "sv_oral_scope_1", "instruction")], [dep("dep_c1", "obj_deliv", "rev_deliv_2", "deliv_r1_script", "fact", "3f9a1c7e5b2d84a6f0e1c3b5d7a9f2e4c6b8d0a2f4e6c8b0d2a4f6e8c0b2d4a68")]),
        ],
      },
    },

    /* ── D04 场地资料 ───────────────────────────────────────────────── */
    {
      id: "rev_venue_1", object_id: "obj_venue", version: 1, created_at: dt("06T02:00:00Z"), change_id: "chg_004",
      payload: {
        title: "场地资料",
        item_order: ["venue_addr", "venue_cond_h", "venue_cond_h2", "venue_cond_leak", "venue_unverified"],
        items: [
          item("venue_addr", "source_statement", { topic: "地址", value: "滨江路 218 号 3 号仓（原棉纺厂北仓）" }, [ref("ev_v_1", "sv_site_1", "supports", { locator: { page: 1 } })]),
          item("venue_cond_h", "user_supplement", { topic: "净高（实测）", value: "北向主厅 7.2 m" }, [ref("ev_v_2", "sv_photos_1", "supports", { asset_id: "a_01", locator: { asset_id: "a_01", caption: "北向通高约 7.2m，保留原有桁架" } })]),
          item("venue_cond_h2", "user_supplement", { topic: "净高（实测）", value: "入口层受限，约 3.1 m" }, [ref("ev_v_3", "sv_photos_1", "supports", { asset_id: "a_03", locator: { asset_id: "a_03" } })]),
          item("venue_cond_leak", "user_supplement", { topic: "已知条件", value: "西墙局部渗水，展墙安装前需做防水处理" }, [ref("ev_v_4", "sv_photos_1", "supports", { asset_id: "a_02" })]),
          item("venue_unverified", "hypothesis", { topic: "载重（未核实）", value: "图纸标注楼面活荷载 350 kg/㎡，现场未复核，不作为布展依据" }, [ref("ev_v_5", "sv_site_1", "supports", { locator: { page: 3 } })]),
        ],
      },
    },

    /* ── D05 品牌资料 ───────────────────────────────────────────────── */
    {
      id: "rev_brand_1", object_id: "obj_brand", version: 1, created_at: dt("04T07:00:00Z"), change_id: "chg_002",
      payload: {
        title: "甲方客户品牌资料",
        item_order: ["brand_pos", "brand_asset_logo", "brand_asset_line", "brand_cond_fee"],
        items: [
          item("brand_pos", "source_statement", { topic: "品牌定位", text: "「让城市记忆可被触摸」——文旅局 2026 年公开表述，强调公共性与可参与。" }, [ref("ev_br_1", "sv_brand_1", "quote")]),
          item("brand_asset_logo", "source_statement", { topic: "文化资产 · 视觉", value: "局徽（横版 SVG）｜开馆物料可用，禁止改色" }, [ref("ev_br_2", "sv_brand_1", "quote", { asset_id: "a_logo", locator: { asset_id: "a_logo" } })]),
          item("brand_asset_line", "source_statement", { topic: "文化资产 · 主视觉", value: "主视觉「江线」AI 文件｜仅限本项目使用，需署名" }, [ref("ev_br_3", "sv_brand_1", "quote")]),
          item("brand_cond_fee", "source_statement", { topic: "使用条件（关联交付）", value: "历史影像档案按张计费，单张上限 2000 元" }, [ref("ev_br_4", "sv_brand_1", "quote")], [dep("dep_b1", "obj_budget", "rev_budget_2", "budget_adopted", "fact", "9c1d3e5f7a9b2c4d6e8f0a1b3c5d7e9f1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d3")]),
        ],
      },
    },

    /* ── D06 受众 ───────────────────────────────────────────────────── */
    {
      id: "rev_audience_1", object_id: "obj_audience", version: 1, created_at: dt("09T11:00:00Z"), change_id: "chg_009",
      payload: {
        title: "受众",
        item_order: ["aud_on_site", "aud_online", "aud_assumption"],
        items: [
          item("aud_on_site", "source_statement", { topic: "亲子家庭与研学团", kind: "现场观众", text: "以亲子家庭与研学团为主，本地市民占多数；外地游客为次要人群。" }, [ref("ev_a_1", "sv_meeting_1", "quote", { locator: { section: "议题 4｜受众" } })]),
          item("aud_online", "reported", { topic: "本地 25–45 岁人群", kind: "传播受众", text: "线上通过文旅局公众号推送一次，以本地 25–45 岁为主。未取得公众号后台画像数据。" }, [ref("ev_a_2", "sv_meeting_1", "reported")]),
          item("aud_assumption", "hypothesis", { topic: "研学团（待确认）", kind: "假设", text: "研学团停留时长可能高于普通观众，需要可分段观看的内容结构。尚未与客户确认。" }, []),
        ],
      },
    },

    /* ── D07 总预算区间（100万 → 60万 的核心例子） ─────────────────── */
    {
      id: "rev_budget_1", object_id: "obj_budget", version: 1, created_at: dt("02T04:10:00Z"), change_id: "chg_001",
      payload: {
        title: "总预算区间",
        item_order: ["client_budget"],
        items: [item("client_budget", "source_statement", { budget_kind: "client", currency: "CNY", min_minor: "100000000", max_minor: "100000000", scope: "本轮项目预算", raw: "100 万元（含设备）" }, [ref("ev_bud_1", "sv_brief_1", "quote", { locator: { heading: "三、预算" } })])],
      },
    },
    {
      id: "rev_budget_2", object_id: "obj_budget", version: 2, created_at: dt("11T07:30:00Z"), change_id: "chg_021",
      payload: {
        title: "总预算区间",
        item_order: ["client_budget", "budget_adopted"],
        items: [
          item("client_budget", "source_statement", { budget_kind: "client", currency: "CNY", min_minor: "100000000", max_minor: "100000000", scope: "本轮项目预算", raw: "100 万元（含设备）" }, [ref("ev_bud_1", "sv_brief_1", "quote", { locator: { heading: "三、预算" } })]),
          item("budget_adopted", "adopted_decision", { budget_kind: "adopted", currency: "CNY", min_minor: "60000000", max_minor: "60000000", scope: "本轮我方执行预算（不含客户设备采购）", raw: "60 万元", decided_by: "主策", rationale: "客户 100 万含其自行采购的设备款；我方执行部分按 60 万推进，设备走客户采购流程。", supersedes_note: "不覆盖客户原始说法" }, [ref("ev_bud_2", "sv_oral_budget_1", "instruction"), ref("ev_bud_3", "sv_brief_1", "contradicts")]),
        ],
      },
    },

    /* ── D08 策划预算分配 ───────────────────────────────────────────── */
    {
      id: "rev_alloc_1", object_id: "obj_alloc", version: 1, created_at: dt("08T03:00:00Z"), change_id: "chg_007",
      payload: {
        title: "策划预算分配",
        item_order: ["alloc_focus", "alloc_restraint"],
        items: [
          item("alloc_focus", "suggestion", { topic: "投入重点", text: "主影片制作与口述史采集为主要投入项。", basis: "按 100 万口径排布" }, [ref("ev_al_1", "sv_brief_1", "supports")]),
          item("alloc_restraint", "suggestion", { topic: "克制项", text: "展墙硬件不做定制，复用场馆既有轨道系统。" }, [ref("ev_al_2", "sv_site_1", "supports", { locator: { page: 2 } })]),
        ],
      },
    },
    {
      id: "rev_alloc_2", object_id: "obj_alloc", version: 2, created_at: dt("11T07:45:00Z"), change_id: "chg_022",
      payload: {
        title: "策划预算分配",
        item_order: ["alloc_focus", "alloc_restraint", "alloc_review_note"],
        items: [
          item("alloc_focus", "suggestion", { topic: "投入重点", text: "按 60 万口径重排：主影片（概念脚本先行）与口述史采集为投入重点，各约 40%。", basis: "按当前采用口径 60 万" }, [ref("ev_al_1", "sv_brief_1", "supports")], [dep("dep_al_1", "obj_budget", "rev_budget_2", "budget_adopted", "derivation", "4e6c8a0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a2c4e6b8d0f2a4c6e8b0d2f4a6c8")]),
          item("alloc_restraint", "suggestion", { topic: "克制项", text: "展墙硬件不做定制，复用场馆既有轨道系统。历史影像档案授权控制在 8 张以内。" }, [ref("ev_al_2", "sv_site_1", "supports", { locator: { page: 2 } })]),
          item("alloc_review_note", "adopted_decision", { topic: "实际审查意见", text: "主策审查：概念脚本阶段先行投入不超过 12 万，其余待方向确认后释放。", decided_by: "主策" }, [ref("ev_al_3", "sv_oral_budget_1", "instruction")]),
        ],
      },
    },

    /* ── D09 时间节点 ───────────────────────────────────────────────── */
    {
      id: "rev_timeline_1", object_id: "obj_timeline", version: 1, created_at: dt("09T11:20:00Z"), change_id: "chg_009",
      payload: {
        title: "时间节点或区间",
        item_order: ["ms_direction", "ms_script", "ms_film", "ms_open", "ms_review_focus"],
        items: [
          item("ms_direction", "source_statement", { event: "提交创意方向", time_kind: "date", date: "2026-12-20", source_note: "客户需求文档" }, [ref("ev_ms_1", "sv_brief_1", "quote", { locator: { heading: "四、时间" } })]),
          item("ms_script", "suggestion", { event: "概念脚本定稿", time_kind: "range", start: "2027-01-05", end: "2027-01-18", basis: "按本轮只交概念脚本倒排；含一轮修改" }, []),
          item("ms_film", "source_statement", { event: "成片交付（顺延至下一轮）", time_kind: "date", date: "2027-02-10", source_note: "客户需求文档；本轮不适用" }, [ref("ev_ms_2", "sv_brief_1", "quote", { locator: { heading: "四、时间" } })]),
          item("ms_open", "source_statement", { event: "开馆日", time_kind: "range", start: "2027-03-15", end: "2027-04-15", source_note: "客户口径「2027 年春季」，具体日期未定" }, [ref("ev_ms_3", "sv_brief_1", "quote")]),
          item("ms_review_focus", "user_supplement", { event: "Review 节点关注内容", text: "12-20 方向评审看叙事结构；01-18 看脚本与分镜是否可执行。" }, []),
        ],
      },
    },

    /* ── D10 客户关键决策节点 ───────────────────────────────────────── */
    {
      id: "rev_clientdec_1", object_id: "obj_clientdec", version: 1, created_at: dt("09T11:40:00Z"), change_id: "chg_009",
      payload: {
        title: "客户关键决策节点",
        item_order: ["cd_signoff", "cd_budget", "cd_pending"],
        items: [
          item("cd_signoff", "source_statement", { role: "李处（文旅局）", decides: "最终验收签字" }, [ref("ev_cd_1", "sv_meeting_1", "quote", { locator: { section: "议题 5｜报批" } })]),
          item("cd_budget", "source_statement", { role: "局办会", decides: "预算追加审批" }, [ref("ev_cd_2", "sv_meeting_1", "quote", { locator: { section: "议题 5｜报批" } })]),
          item("cd_pending", "user_supplement", { topic: "待客户确认", text: "主影片是否允许分段（供研学团分段观看）——10 月 9 日提出，尚未答复。" }, []),
        ],
      },
    },

    /* ── D11 合作类型 ───────────────────────────────────────────────── */
    {
      id: "rev_coop_1", object_id: "obj_coop", version: 1, created_at: dt("02T04:20:00Z"), change_id: "chg_001",
      payload: {
        title: "合作类型",
        item_order: ["coop_type"],
        items: [item("coop_type", "source_statement", { value: "直接委托", note: "客户需求文档以委托口径编写，未走公开招标流程" }, [ref("ev_co_1", "sv_brief_1", "supports")])],
      },
    },

    /* ── D14 会议纪要 ───────────────────────────────────────────────── */
    {
      id: "rev_meetings_1", object_id: "obj_meetings", version: 1, created_at: dt("09T12:00:00Z"), change_id: "chg_009",
      payload: {
        title: "与甲方的会议纪要",
        item_order: ["mt_kickoff"],
        items: [item("mt_kickoff", "source_statement", { meeting: "开工会", meeting_at: "2026-10-09T14:00:00+08:00", focus: "交付形态、受众、报批路径", captures: ["cap_1", "cap_2", "cap_3"], note: "本纪要只收录议题 2、4、5 的转写段落，非全文" }, [ref("ev_mt_1", "sv_meeting_1", "quote", { locator: { section: "议题 2/4/5" } })])],
      },
    },

    /* ── D15 客户 Q&A 问题表（R05 直接读它） ────────────────────────── */
    {
      id: "rev_qa_1", object_id: "obj_qa", version: 1, created_at: dt("10T02:00:00Z"), change_id: "chg_012",
      payload: {
        title: "客户 Q&A 问题表",
        item_order: ["q_film_segment", "q_device", "q_oral_count", "q_wall_swap"],
        items: [
          item("q_film_segment", "user_supplement", {
            question: "主影片是否允许分段，供研学团分段观看？",
            status: "待答复", follow_up: "主策 → 李处", related_object_ids: ["obj_audience"],
            answer: null, answer_basis: null,
          }, []),
          item("q_device", "user_supplement", {
            question: "100 万中的设备款是否由客户自行采购？",
            status: "已答复", follow_up: "主策 → BD",
            answer: "是。设备由局里走自己的采购流程，我方执行部分按 60 万。",
            answer_basis: "主策口述 10 月 11 日", related_object_ids: ["obj_budget"],
          }, [ref("ev_q_1", "sv_oral_budget_1", "instruction")]),
          item("q_oral_count", "user_supplement", {
            question: "口述史采集的 12 位受访者由谁确定？",
            status: "待答复", follow_up: "BD → 李处", related_object_ids: ["obj_deliv"],
            answer: null, answer_basis: null,
          }, []),
          item("q_wall_swap", "user_supplement", {
            question: "展墙图文是否允许后期更换内容？",
            status: "不适用", note: "本轮只做排版稿，不涉及更换机制；已记录不适用，不是遗漏。",
            related_object_ids: ["obj_deliv"], answer: null, answer_basis: null,
          }, []),
        ],
      },
    },

    /* ── D17 主策策略 ───────────────────────────────────────────────── */
    {
      id: "rev_strategy_1", object_id: "obj_strategy", version: 1, created_at: dt("10T06:00:00Z"), change_id: "chg_014",
      payload: {
        title: "主策策略",
        item_order: ["st_goal", "st_approach", "st_research", "st_options"],
        items: [
          item("st_goal", "source_statement", { topic: "本轮目标", text: "在 12-20 方向评审前，形成一条可被客户接受的「城市记忆」叙事主线。" }, [ref("ev_st_1", "sv_brief_1", "quote")]),
          item("st_approach", "suggestion", { topic: "策略", text: "以「三个历史断面 + 一条江线」组织空间与影像，让观众沿动线完成时间推移。" }, [ref("ev_st_2", "sv_brand_1", "supports", { asset_id: "a_logo" })]),
          item("st_research", "suggestion", { topic: "调研判断", text: "同类展陈常见问题是「信息墙化」，本次以口述史音频打断密度，降低阅读负担。" }, []),
          item("st_options", "suggestion", { topic: "方向候选", text: "A. 江线为轴（推荐）｜B. 以人物口述串联｜C. 以物件档案陈列为主。取舍依据：A 与场馆动线最贴合，B 依赖口述史采集进度。" }, []),
        ],
      },
    },

    /* ── D18 交付细节（成片 → 概念脚本） ───────────────────────────── */
    {
      id: "rev_deliv_1", object_id: "obj_deliv", version: 1, created_at: dt("02T04:30:00Z"), change_id: "chg_001",
      payload: {
        title: "交付细节",
        item_order: ["deliv_r1_film", "deliv_r1_wall"],
        items: [
          item("deliv_r1_film", "source_statement", { round_key: "r1", deliverable: "主影片", granularity: "成片", spec: "8 分钟，3840×2160，H.264", quantity: 1, limits: "含 3 次修改", external_dependencies: "历史影像档案授权（按张计费）" }, [ref("ev_d_1", "sv_brief_1", "quote", { locator: { heading: "二、交付要求" } })]),
          item("deliv_r1_wall", "source_statement", { round_key: "r1", deliverable: "展墙图文", granularity: "排版稿", spec: "3 面墙，300dpi", quantity: 3 }, [ref("ev_d_2", "sv_brief_1", "quote", { locator: { heading: "二、交付要求" } })]),
        ],
      },
    },
    {
      id: "rev_deliv_2", object_id: "obj_deliv", version: 2, created_at: dt("13T09:10:00Z"), change_id: "chg_031",
      payload: {
        title: "交付细节",
        item_order: ["deliv_r1_script", "deliv_r1_wall", "deliv_r1_film_deferred", "deliv_out_of_scope"],
        items: [
          item("deliv_r1_script", "adopted_decision", {
            round_key: "r1", deliverable: "主影片", granularity: "概念脚本", spec: "含分镜与旁白大纲，不含成片制作", quantity: 1,
            limits: "含 2 次修改", external_dependencies: "口述史采集素材包（不少于 12 位受访者）",
            applies_to: "全项目本轮通用要求", decided_by: "主策",
          }, [ref("ev_d_3", "sv_oral_scope_1", "instruction")]),
          item("deliv_r1_wall", "source_statement", { round_key: "r1", deliverable: "展墙图文", granularity: "排版稿", spec: "3 面墙，300dpi", quantity: 3 }, [ref("ev_d_2", "sv_brief_1", "quote", { locator: { heading: "二、交付要求" } })]),
          item("deliv_r1_film_deferred", "reported", { round_key: "r2", deliverable: "主影片", granularity: "成片", spec: "8 分钟，3840×2160，H.264", note: "本轮不适用，顺延至下一轮；保留客户原始要求" }, [ref("ev_d_4", "sv_brief_1", "quote")]),
          item("deliv_out_of_scope", "user_supplement", { topic: "不做范围", text: "本轮不含设备采购、不含展陈施工、不含版权买断。" }, []),
        ],
      },
    },

    /* ── D19 内外部资源 ─────────────────────────────────────────────── */
    {
      id: "rev_resources_1", object_id: "obj_resources", version: 1, created_at: dt("10T07:00:00Z"), change_id: "chg_015",
      payload: {
        title: "内外部资源",
        item_order: ["res_zhou", "res_lin", "res_studio"],
        items: [
          item("res_zhou", "user_supplement", { name: "周叙（导演）", capability: "纪录片长片、口述史采集", works: "《河口》《四点半的桥》", availability: "已核实可用", participation: "已确认参与", status: "confirmed" }, []),
          item("res_lin", "user_supplement", { name: "林见（视觉设计）", capability: "展陈视觉、图文书版", works: "市博物馆常设展视觉", availability: "档期需确认（12 月中旬前）", participation: "候选", status: "candidate" }, []),
          item("res_studio", "reported", { name: "青苔录音棚", capability: "配音与混音", works: "—", availability: "未核实", participation: "候选", status: "candidate", note: "由 BD 推荐，尚未核实档期与报价" }, []),
        ],
      },
    },

    /* ── D20 职责边界 ───────────────────────────────────────────────── */
    {
      id: "rev_resp_1", object_id: "obj_resp", version: 1, created_at: dt("09T12:30:00Z"), change_id: "chg_009",
      payload: {
        title: "职责边界",
        item_order: ["resp_lead", "resp_bd", "resp_signoff", "resp_assign_zhou"],
        items: [
          item("resp_lead", "user_supplement", { role: "主策", who: "本人", duty: "策略、方向、成片质量把关" }, []),
          item("resp_bd", "user_supplement", { role: "BD 接口", who: "陈可", duty: "客户沟通、合同与商务" }, []),
          item("resp_signoff", "user_supplement", { role: "内部拍板人", who: "本人", duty: "交付取舍与预算调整的最终确认" }, []),
          item("resp_assign_zhou", "suggestion", { role: "主影片", who: "周叙", duty: "概念脚本与后续成片导演", note: "建议分工，待正式承接确认" }, [], [dep("dep_r_1", "obj_resources", "rev_resources_1", "res_zhou", "fact", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b")]),
        ],
      },
    },

    /* ── D22 风险点 ─────────────────────────────────────────────────── */
    {
      id: "rev_risks_1", object_id: "obj_risks", version: 1, created_at: dt("10T07:30:00Z"), change_id: "chg_016",
      payload: {
        title: "风险点",
        item_order: ["risk_oral", "risk_leak", "risk_budget"],
        items: [
          item("risk_oral", "suggestion", { risk: "口述史采集进度可能拖累概念脚本定稿", trigger: "12 位受访者中已确定不足 4 位", impact: "影响 2027-01-18 脚本定稿", response: "先按已有受访者出脚本框架，素材包到位后补全", decision: "待处理", to_verify: "受访者名单归属（见 Q&A）" }, [], [dep("dep_k_1", "obj_qa", "rev_qa_1", "q_oral_count", "derivation", "5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7")]),
          item("risk_leak", "user_supplement", { risk: "西墙渗水影响展墙安装", trigger: "梅雨季节前未完成防水", impact: "展墙图文安装工期压缩", response: "要求场馆方在 11 月底前完成防水；纳入交付前置条件", decision: "已接受（由客户处理）" }, [ref("ev_k_1", "sv_photos_1", "supports", { asset_id: "a_02" })]),
          item("risk_budget", "adopted_decision", { risk: "按 60 万推进后，成片顺延可能引发客户误解", trigger: "客户以为 100 万含成片制作", impact: "验收口径不一致", response: "在 Debrief 中明确本轮交付边界，并保留客户原始要求记录", decision: "已处理", decided_by: "主策" }, [ref("ev_k_2", "sv_oral_budget_1", "instruction")]),
        ],
      },
    },

    /* ── 内部：成果编写要求（expression_guide） ────────────────────── */
    {
      id: "rev_guide_1", object_id: "obj_guide_r01", version: 1, created_at: dt("12T03:10:00Z"), change_id: "chg_025",
      payload: {
        title: "成果编写要求 · 主策 Debrief",
        item_order: ["guide_budget_concise"],
        items: [item("guide_budget_concise", "adopted_decision", {
          scope_review: "R01 主策 Debrief", block_ids: ["budget"],
          requirement: "预算段落保持简明：只说明本轮采用口径，不铺开两个金额的对比。",
          instruction_source: "主策口述 10 月 12 日", applies_to: "表达要求，不改变业务事实",
        }, [ref("ev_g_1", "sv_oral_style_1", "instruction")])],
      },
    },

    /* ══════════════════ review 成果 ══════════════════════════════════ */
    {
      id: "rev_r01_1", object_id: "obj_r01", version: 1, created_at: dt("09T14:00:00Z"), change_id: "chg_010",
      payload: {
        title: "主策 Debrief",
        block_order: ["why", "goal", "audience", "who_decides", "scope", "budget"],
        blocks: [
          { block_id: "why", markdown: "客户今年启动本项目，与年底前必须完成立项采购的额度窗口直接相关。文旅局拟借滨江旧仓改造建立常设展陈的首期叙事框架。" },
          { block_id: "goal", markdown: "要在开馆日交付可循环播放的主影片与展墙图文，并形成一条能被本地市民识别、能被历史表述审查通过的「城市记忆」主线。" },
          { block_id: "audience", markdown: "现场以亲子家庭与研学团为主，本地市民占多数；线上通过文旅局公众号触达一次。" },
          { block_id: "who_decides", markdown: "客户侧最终验收由李处签字，预算追加需局办会通过。内部交付取舍与预算调整由主策确认。" },
          { block_id: "scope", markdown: "本轮交付包含主影片与 3 面展墙图文。主影片在首期的形态由交付细节对象界定。" },
          { block_id: "budget", markdown: "本轮我方执行预算按 **60 万元** 推进。" },
        ],
      },
      block_lineage: {
        why: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_background" }, { object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_why_now" }] },
        goal: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_goal" }, { object_id: "obj_brief", revision_id: "rev_brief_1", item_id: "req_film" }] },
        audience: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_audience", revision_id: "rev_audience_1", item_id: "aud_on_site" }, { object_id: "obj_audience", revision_id: "rev_audience_1", item_id: "aud_online" }] },
        who_decides: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_clientdec", revision_id: "rev_clientdec_1", item_id: "cd_signoff" }, { object_id: "obj_resp", revision_id: "rev_resp_1", item_id: "resp_signoff" }] },
        scope: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_deliv", revision_id: "rev_deliv_1", item_id: "deliv_r1_film" }] },
        budget: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_budget", revision_id: "rev_budget_1", item_id: "client_budget" }] },
      },
    },
    {
      id: "rev_r01_2", object_id: "obj_r01", version: 2, created_at: dt("12T03:30:00Z"), change_id: "chg_026",
      payload: {
        title: "主策 Debrief",
        block_order: ["why", "goal", "audience", "who_decides", "scope", "budget"],
        blocks: [
          { block_id: "why", markdown: "客户今年启动本项目，与年底前必须完成立项采购的额度窗口直接相关。文旅局拟借滨江旧仓改造建立常设展陈的首期叙事框架。" },
          { block_id: "goal", markdown: "要在开馆日交付可循环播放的主影片与展墙图文，并形成一条能被本地市民识别、能被历史表述审查通过的「城市记忆」主线。" },
          { block_id: "audience", markdown: "现场以亲子家庭与研学团为主，本地市民占多数；线上通过文旅局公众号触达一次。" },
          { block_id: "who_decides", markdown: "客户侧最终验收由李处签字，预算追加需局办会通过。内部交付取舍与预算调整由主策确认。" },
          { block_id: "scope", markdown: "本轮交付包含主影片与 3 面展墙图文。主影片在首期的形态由交付细节对象界定。" },
          { block_id: "budget", markdown: "本轮我方执行预算按 **60 万元** 推进。" },
        ],
      },
      block_lineage: {
        why: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_background" }] },
        goal: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_goal" }] },
        audience: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_audience", revision_id: "rev_audience_1", item_id: "aud_on_site" }] },
        who_decides: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_clientdec", revision_id: "rev_clientdec_1", item_id: "cd_signoff" }] },
        // 这一段尚未随 D18 的新版同步：演示「依据已变化／成果尚未同步」
        scope: { last_written_revision_id: "rev_r01_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_deliv", revision_id: "rev_deliv_1", item_id: "deliv_r1_film" }] },
        budget: {
          last_written_revision_id: "rev_r01_2", applied_cause_change_ids: ["chg_021", "chg_025"],
          basis: [
            { object_id: "obj_budget", revision_id: "rev_budget_2", item_id: "budget_adopted" },
            { object_id: "obj_guide_r01", revision_id: "rev_guide_1", item_id: "guide_budget_concise" },
          ],
        },
      },
    },
    {
      id: "rev_r02_1", object_id: "obj_r02", version: 1, created_at: dt("09T14:10:00Z"), change_id: "chg_010",
      payload: {
        title: "推进要素",
        block_order: ["plan_deliver", "plan_nodes", "plan_owners"],
        blocks: [
          { block_id: "plan_deliver", markdown: "本轮推进围绕主影片与展墙图文展开。主影片首期形态为**成片**，含 3 次修改。" },
          { block_id: "plan_nodes", markdown: "- **2026-12-20** 创意方向评审\n- **2027-01-18** 概念脚本定稿（含一轮修改）\n- **2027-02-10** 成片交付（本轮顺延）" },
          { block_id: "plan_owners", markdown: "主影片由周叙承接，展墙图文的专业负责人待定；客户侧验收由李处签字。" },
        ],
      },
      block_lineage: {
        plan_deliver: { last_written_revision_id: "rev_r02_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_deliv", revision_id: "rev_deliv_1", item_id: "deliv_r1_film" }] },
        plan_nodes: { last_written_revision_id: "rev_r02_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_timeline", revision_id: "rev_timeline_1", item_id: "ms_script" }, { object_id: "obj_timeline", revision_id: "rev_timeline_1", item_id: "ms_direction" }] },
        plan_owners: { last_written_revision_id: "rev_r02_1", applied_cause_change_ids: ["chg_010"], basis: [{ object_id: "obj_resp", revision_id: "rev_resp_1", item_id: "resp_assign_zhou" }] },
      },
    },
    {
      id: "rev_r03_1", object_id: "obj_r03", version: 1, created_at: dt("11T03:00:00Z"), change_id: "chg_023",
      payload: {
        title: "创意审查结果",
        block_order: ["cr_target", "cr_direction", "cr_investment", "cr_pending"],
        blocks: [
          { block_id: "cr_target", markdown: "本轮策略目标是在 12-20 方向评审前形成可被客户接受的叙事主线。策略对象已给出目标与判断，尚未有正式审查结论。" },
          { block_id: "cr_direction", markdown: "方向候选为「江线为轴」「人物口述串联」「物件档案陈列」三案。主策倾向 A 案，理由是与场馆动线贴合，且不依赖口述史采集进度。" },
          { block_id: "cr_investment", markdown: "投入重点为主影片与口述史采集，各约 40%。概念脚本阶段先行投入不超过 12 万元，其余待方向确认后释放。" },
          { block_id: "cr_pending", markdown: "待讨论：口述史受访者名单尚未确定，可能影响脚本定稿节点。" },
        ],
      },
      block_lineage: {
        cr_target: { last_written_revision_id: "rev_r03_1", applied_cause_change_ids: ["chg_023"], basis: [{ object_id: "obj_strategy", revision_id: "rev_strategy_1", item_id: "st_goal" }] },
        cr_direction: { last_written_revision_id: "rev_r03_1", applied_cause_change_ids: ["chg_023"], basis: [{ object_id: "obj_strategy", revision_id: "rev_strategy_1", item_id: "st_options" }] },
        cr_investment: { last_written_revision_id: "rev_r03_1", applied_cause_change_ids: ["chg_022", "chg_023"], basis: [{ object_id: "obj_alloc", revision_id: "rev_alloc_2", item_id: "alloc_focus" }, { object_id: "obj_alloc", revision_id: "rev_alloc_2", item_id: "alloc_review_note" }] },
        cr_pending: { last_written_revision_id: "rev_r03_1", applied_cause_change_ids: ["chg_023"], basis: [{ object_id: "obj_risks", revision_id: "rev_risks_1", item_id: "risk_oral" }] },
      },
    },
    {
      id: "rev_r04_1", object_id: "obj_r04", version: 1, created_at: dt("11T04:00:00Z"), change_id: "chg_027",
      payload: {
        title: "创作者 Brief · 周叙（导演）",
        block_order: ["cb_background", "cb_task", "cb_deliver", "cb_schedule", "cb_collab", "cb_limits"],
        blocks: [
          { block_id: "cb_background", markdown: "市文旅局拟在滨江旧仓改造常设展厅「城市记忆」，2027 年春季开馆。首期需完成一支可在开馆日循环播放的主影片，并建立展厅的首期叙事框架。" },
          { block_id: "cb_task", markdown: "本轮请你完成主影片的**概念脚本**：以「三个历史断面 + 一条江线」为主线，形成分镜与旁白大纲，并给出可执行的现场拍摄构想。" },
          { block_id: "cb_deliver", markdown: "交付物：8 分钟主影片 1 支，3840×2160，H.264 格式。含 3 次修改。历史影像档案授权按张计费。" },
          { block_id: "cb_schedule", markdown: "**2027-01-18** 前完成脚本定稿；**2026-12-20** 方向评审时提交叙事结构初稿。" },
          { block_id: "cb_collab", markdown: "你负责主影片的概念与后续成片导演；展墙图文由我方另行安排。口述史采集的受访者名单由客户确认后提供。" },
          { block_id: "cb_limits", markdown: "历史影像档案授权按张计费，单张上限 2000 元。" },
        ],
      },
      block_lineage: {
        cb_background: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_bd", revision_id: "rev_bd_2", item_id: "bd_background" }, { object_id: "obj_audience", revision_id: "rev_audience_1", item_id: "aud_on_site" }] },
        cb_task: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_strategy", revision_id: "rev_strategy_1", item_id: "st_approach" }] },
        cb_deliver: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_deliv", revision_id: "rev_deliv_1", item_id: "deliv_r1_film" }, { object_id: "obj_brand", revision_id: "rev_brand_1", item_id: "brand_cond_fee" }] },
        cb_schedule: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_timeline", revision_id: "rev_timeline_1", item_id: "ms_script" }] },
        cb_collab: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_resp", revision_id: "rev_resp_1", item_id: "resp_assign_zhou" }, { object_id: "obj_resources", revision_id: "rev_resources_1", item_id: "res_zhou" }] },
        cb_limits: { last_written_revision_id: "rev_r04_1", applied_cause_change_ids: ["chg_027"], basis: [{ object_id: "obj_brand", revision_id: "rev_brand_1", item_id: "brand_cond_fee" }] },
      },
    },
    {
      id: "rev_r04b_1", object_id: "obj_r04b", version: 1, created_at: dt("11T04:20:00Z"), change_id: "chg_028",
      payload: {
        title: "创作者 Brief · 林见（视觉设计）",
        block_order: ["cb_background", "cb_task", "cb_deliver", "cb_schedule"],
        blocks: [
          { block_id: "cb_background", markdown: "「城市记忆」常设展厅首期，需要 3 面展墙的图文排版稿。" },
          { block_id: "cb_task", markdown: "以「三个历史断面」组织图文层级，控制单面墙的阅读密度，为口述史音频留出呼吸空间。" },
          { block_id: "cb_deliver", markdown: "交付物：3 面展墙图文排版稿，300dpi。含 2 次修改。" },
          { block_id: "cb_schedule", markdown: "**2027-01-18** 前提交初稿，与脚本定稿节点同步。" },
        ],
      },
      block_lineage: {
        cb_background: { last_written_revision_id: "rev_r04b_1", applied_cause_change_ids: ["chg_028"], basis: [{ object_id: "obj_brief", revision_id: "rev_brief_1", item_id: "req_wall" }] },
        cb_task: { last_written_revision_id: "rev_r04b_1", applied_cause_change_ids: ["chg_028"], basis: [{ object_id: "obj_strategy", revision_id: "rev_strategy_1", item_id: "st_research" }] },
        cb_deliver: { last_written_revision_id: "rev_r04b_1", applied_cause_change_ids: ["chg_028"], basis: [{ object_id: "obj_deliv", revision_id: "rev_deliv_2", item_id: "deliv_r1_wall" }] },
        cb_schedule: { last_written_revision_id: "rev_r04b_1", applied_cause_change_ids: ["chg_028"], basis: [{ object_id: "obj_timeline", revision_id: "rev_timeline_1", item_id: "ms_script" }] },
      },
    },

    /* ── YU+ Dev 项目：一个轻量项目，演示项目隔离 ─────────────────── */
    {
      id: "rev_yd_deliv_1", object_id: "obj_yd_deliv", version: 1, created_at: dt("12T14:31:00Z"), change_id: "chg_104",
      payload: {
        title: "交付细节",
        item_order: ["yd_scope"],
        items: [item("yd_scope", "adopted_decision", { round_key: "r1", deliverable: "前端只读页面", granularity: "可点击原型", spec: "覆盖 draft / review / 材料 / 历史四条浏览路径" }, [])],
      },
    },
    {
      id: "rev_yd_risk_1", object_id: "obj_yd_risk", version: 1, created_at: dt("12T14:31:00Z"), change_id: "chg_104",
      payload: {
        title: "风险点",
        item_order: ["yd_stale"],
        items: [item("yd_stale", "suggestion", { risk: "示例数据被误当真实项目材料", response: "所有页面标注「示例数据」；不接入真实飞书凭证" }, [])],
      },
    },
  ];

  /* ══════════════════════ changes · decisions · checks ══════════════════ */

  const change = (id, seq, command, effect, reason, at, causal, refs) => ({
    id, seq, project_id: "prj_city", command, effect, reason,
    actor: { kind: "agent", via: "codex" }, causal_change_ids: causal || [], changed_refs: refs || [], created_at: at,
  });

  const changes = [
    change("chg_001", 1, "draft.apply", "changed", "建立首期 draft 对象（来源需求文档与品牌清单）", dt("02T04:35:00Z"), [], [{ layer: "draft", object_id: "obj_bd" }, { layer: "draft", object_id: "obj_brief" }, { layer: "draft", object_id: "obj_budget" }, { layer: "draft", object_id: "obj_deliv" }]),
    change("chg_002", 2, "source.import", "changed", "收录品牌资产清单", dt("04T06:10:00Z"), []),
    change("chg_003", 3, "source.import", "changed", "收录场馆平面图 PDF", dt("05T02:00:00Z"), []),
    change("chg_004", 4, "source.import", "changed", "收录现场勘察照片并提取场地条件", dt("06T01:30:00Z"), [], [{ layer: "draft", object_id: "obj_venue" }]),
    change("chg_005", 5, "source.import", "changed", "收录开工会纪要节选", dt("09T10:20:00Z"), []),
    change("chg_006", 6, "source.import", "changed", "登记 2024 年概念提案（外部路径）", dt("03T06:00:00Z"), []),
    change("chg_007", 7, "draft.apply", "changed", "建立 D08 策划预算分配（100 万口径）", dt("08T03:00:00Z"), [], [{ layer: "draft", object_id: "obj_alloc" }]),
    change("chg_008", 8, "draft.apply", "changed", "补齐 D01 BD 同步信息的分主题条目", dt("09T12:40:00Z"), [], [{ layer: "draft", object_id: "obj_bd" }]),
    change("chg_009", 9, "draft.apply", "changed", "根据开工会纪要建立受众、时间、决策角色、职责与会议纪要", dt("09T13:00:00Z"), ["chg_005"], [{ layer: "draft", object_id: "obj_audience" }, { layer: "draft", object_id: "obj_timeline" }, { layer: "draft", object_id: "obj_clientdec" }, { layer: "draft", object_id: "obj_resp" }, { layer: "draft", object_id: "obj_meetings" }]),
    change("chg_010", 10, "review.publish", "changed", "首次生成 R01 Debrief 与 R02 推进要素", dt("09T14:10:00Z"), ["chg_001", "chg_008", "chg_009"], [{ layer: "review", object_id: "obj_r01" }, { layer: "review", object_id: "obj_r02" }]),
    change("chg_012", 12, "draft.apply", "changed", "建立 D15 客户 Q&A 问题表", dt("10T02:00:00Z"), [], [{ layer: "draft", object_id: "obj_qa" }]),
    change("chg_014", 14, "draft.apply", "changed", "建立 D17 主策策略与方向候选", dt("10T06:00:00Z"), ["chg_009"], [{ layer: "draft", object_id: "obj_strategy" }]),
    change("chg_015", 15, "draft.apply", "changed", "建立 D19 内外部资源（候选与已确认）", dt("10T07:00:00Z"), [], [{ layer: "draft", object_id: "obj_resources" }]),
    change("chg_016", 16, "draft.apply", "changed", "建立 D22 风险点", dt("10T07:30:00Z"), [], [{ layer: "draft", object_id: "obj_risks" }]),
    change("chg_020", 20, "source.import", "changed", "收录主策口述：预算按 60 万推进", dt("11T07:15:00Z"), []),
    change("chg_021", 21, "draft.apply", "changed", "D07 新增采用决定条目：本轮按 60 万；保留客户原始 100 万说法", dt("11T07:30:00Z"), ["chg_020"], [{ layer: "draft", object_id: "obj_budget" }]),
    change("chg_022", 22, "draft.apply", "changed", "D08 按 60 万口径重排分配并记录审查意见", dt("11T07:45:00Z"), ["chg_021"], [{ layer: "draft", object_id: "obj_alloc" }]),
    change("chg_023", 23, "review.publish", "changed", "生成 R03 创意审查结果", dt("11T03:00:00Z"), ["chg_014", "chg_022"], [{ layer: "review", object_id: "obj_r03" }]),
    change("chg_024", 24, "source.import", "changed", "收录主策口述：Debrief 预算段要求简明", dt("12T03:05:00Z"), []),
    change("chg_025", 25, "draft.apply", "changed", "新增成果编写要求（expression_guide → R01.budget）", dt("12T03:10:00Z"), ["chg_024"], [{ layer: "draft", object_id: "obj_guide_r01" }]),
    change("chg_026", 26, "review.publish", "changed", "R01 第 2 版：预算段按编写要求精简", dt("12T03:30:00Z"), ["chg_021", "chg_025"], [{ layer: "review", object_id: "obj_r01" }]),
    change("chg_027", 27, "review.publish", "changed", "生成 R04 创作者 Brief（周叙）", dt("11T04:00:00Z"), ["chg_010", "chg_015", "chg_016"], [{ layer: "review", object_id: "obj_r04" }]),
    change("chg_028", 28, "review.publish", "changed", "生成 R04 创作者 Brief（林见）", dt("11T04:20:00Z"), ["chg_010", "chg_015"], [{ layer: "review", object_id: "obj_r04b" }]),
    change("chg_029", 29, "source.import", "changed", "飞书需求文档远端 revision 更新，收录第 2 版快照（新增口述史素材包要求）", dt("13T08:02:00Z"), [], [{ layer: "draft", object_id: "obj_brief" }]),
    change("chg_030", 30, "source.import", "changed", "收录主策口述：本轮只交概念脚本", dt("13T09:05:00Z"), []),
    change("chg_031", 31, "draft.apply", "changed", "D18 本轮交付由「成片」改为「概念脚本」，成片顺延至下一轮", dt("13T09:12:40Z"), ["chg_030"], [{ layer: "draft", object_id: "obj_deliv" }]),
    // 一次真正没有变化的提交：noop 回执，不产生新版本
    change("chg_032", 32, "source.import", "noop", "品牌资产清单远端 revision 未变化，快照复用", dt("13T08:02:30Z"), []),
  ];

  /* ── 展示优化用模拟记录：补齐全部 23 类业务对象 ───────────────────────── */
  const fixtureTime = "2026-10-16T06:30:00Z";
  for (const [index, fixture] of DESIGN_FIXTURES.entries()) {
    const sourceId = `src_design_${fixture.key}`;
    const snapshotId = `sv_design_${fixture.key}_1`;
    const revisionId = `rev_${fixture.key}_1`;
    const changeId = `chg_design_${fixture.key}`;
    const source = {
      id:sourceId, project_id:"prj_city", provider:fixture.provider, resource_type:fixture.provider === "web" ? "link" : "docx",
      provider_key:`demo:${fixture.key}`, canonical_url:`./source.html?id=${sourceId}`,
      cached_title:fixture.sourceTitle, latest_snapshot_id:snapshotId,
      last_checked_at:null, created_at:fixtureTime, archived_at:null,
    };
    sources.push(source);
    source_versions.push({
      id:snapshotId, source_id:sourceId, version:1, provider_revision:null,
      capture_scope:{mode:"full"}, title_at_capture:fixture.sourceTitle,
      captured_at:fixtureTime, recorded_at:fixtureTime, change_id:changeId,
      body_format:"text", body_text:"【模拟材料，仅供页面展示优化】\n\n" + fixture.body,
      assets:[],
    });
    const items = fixture.items.map((entry) => {
      const evidence = entry.kind === "source_statement" ? "quote" : entry.kind === "adopted_decision" ? "instruction" : entry.kind === "reported" ? "reported" : "supports";
      const refs = entry.noSource ? [] : [ref(`ev_design_${entry.id}`, snapshotId, evidence)];
      if (entry.extraSource) refs.push(ref(`ev_design_${entry.id}_extra`, entry.extraSource, "supports"));
      return item(entry.id, entry.kind, entry.data, refs);
    });
    object_revisions.push({id:revisionId,object_id:fixture.objectId,version:1,created_at:fixtureTime,change_id:changeId,
      payload:{title:fixture.title,item_order:items.map((it)=>it.item_id),items}});
    objects.find((o)=>o.id===fixture.objectId).current_revision_id = revisionId;
    changes.push(change(changeId, 33 + index, "draft.apply", "changed", `补充${fixture.title}模拟记录`, fixtureTime, [], [{layer:"draft",object_id:fixture.objectId}]));
  }

  // Preserve the existing day-level revision while adding minute-level examples.
  const scheduleSourceId = "src_design_schedule";
  sources.push({id:scheduleSourceId,project_id:"prj_city",provider:"feishu",resource_type:"docx",provider_key:"demo:schedule",
    canonical_url:`./source.html?id=${scheduleSourceId}`,cached_title:"项目评审与素材交接安排（模拟）",latest_snapshot_id:"sv_design_schedule_1",last_checked_at:null,created_at:fixtureTime,archived_at:null});
  source_versions.push({id:"sv_design_schedule_1",source_id:scheduleSourceId,version:1,provider_revision:null,capture_scope:{mode:"full"},title_at_capture:"项目评审与素材交接安排（模拟）",
    captured_at:fixtureTime,recorded_at:fixtureTime,change_id:"chg_design_schedule",body_format:"text",
    body_text:"【模拟材料，仅供页面展示优化】\n方向评审讨论安排在 2026-12-20 14:30 至 16:00，议题为叙事结构与历史断面。\n第一批口述史素材交接截止为 2027-01-05 10:00，主策核对音频、转写和授权状态。\n这些时分记录与原有按天安排并存，不改变原有交付范围。",assets:[]});
  const timelineBase = object_revisions.find((r)=>r.id==="rev_timeline_1");
  const minuteItems = [
    item("ms_direction_meeting","user_supplement",{event:"方向评审讨论",time_kind:"range",start:"2026-12-20T14:30",end:"2026-12-20T16:00",source_note:"讨论叙事结构与历史断面"},[ref("ev_design_schedule_meeting","sv_design_schedule_1","supports")]),
    item("ms_material_handoff","user_supplement",{event:"首批口述史素材交接",time_kind:"datetime",date:"2027-01-05T10:00",source_note:"核对音频、转写和授权状态"},[ref("ev_design_schedule_handoff","sv_design_schedule_1","supports")]),
  ];
  object_revisions.push({id:"rev_timeline_2",object_id:"obj_timeline",version:2,created_at:fixtureTime,change_id:"chg_design_schedule",
    payload:{...timelineBase.payload,item_order:[...timelineBase.payload.item_order,...minuteItems.map((it)=>it.item_id)],items:[...timelineBase.payload.items,...minuteItems]}});
  objects.find((o)=>o.id==="obj_timeline").current_revision_id="rev_timeline_2";
  changes.push(change("chg_design_schedule",39,"draft.apply","changed","补齐 23 类对象展示数据，并补充分钟级时间安排",fixtureTime,[],[{layer:"draft",object_id:"obj_timeline"}]));
  projects.find((p)=>p.id==="prj_city").updated_at=fixtureTime;
  project_activity.prj_city={change_id:"chg_design_schedule",summary:"23 类业务对象模拟内容已齐备，可逐项优化展示",at:fixtureTime};

  const decisions = [
    {
      id: "dec_budget_60", project_id: "prj_city", change_id: "chg_021",
      statement: "本轮项目预算按 60 万元（人民币）推进，不采用需求文档中的 100 万元口径。",
      decided_by: "主策",
      instruction_source_version_id: "sv_oral_budget_1",
      rationale: "客户需求文档的 100 万元包含其自行采购的设备款；我方执行部分为 60 万元，设备由客户走自身采购流程。",
      affected_refs: [
        { layer: "draft", object_id: "obj_budget", item_id: "budget_adopted" },
        { layer: "draft", object_id: "obj_alloc", item_id: "alloc_focus" },
        { layer: "review", object_id: "obj_r01", block_id: "budget" },
        { layer: "review", object_id: "obj_r03", block_id: "cr_investment" },
      ],
      supersedes_id: null, created_at: dt("11T07:30:00Z"),
    },
    {
      id: "dec_scope_script", project_id: "prj_city", change_id: "chg_031",
      statement: "本轮主影片交付形态由「成片」调整为「概念脚本」，成片顺延至第二轮。",
      decided_by: "主策",
      instruction_source_version_id: "sv_oral_scope_1",
      rationale: "口述史采集尚未完成，成片制作前置条件不足；先锁定概念脚本可保住 12-20 方向评审节点。",
      affected_refs: [
        { layer: "draft", object_id: "obj_deliv", item_id: "deliv_r1_script" },
        { layer: "draft", object_id: "obj_brief", item_id: "correction_1" },
        { layer: "review", object_id: "obj_r02", block_id: "plan_deliver" },
        { layer: "review", object_id: "obj_r04", block_id: "cb_deliver" },
      ],
      supersedes_id: null, created_at: dt("13T09:12:40Z"),
    },
    {
      id: "dec_style_budget", project_id: "prj_city", change_id: "chg_025",
      statement: "R01 主策 Debrief 的预算段落保持简明，不铺开两个金额的对比。",
      decided_by: "主策",
      instruction_source_version_id: "sv_oral_style_1",
      rationale: "客户关注的是我方实际执行口径，两个金额并列会造成阅读负担。属于表达要求，不改变业务事实。",
      affected_refs: [{ layer: "review", object_id: "obj_r01", block_id: "budget" }],
      supersedes_id: null, created_at: dt("12T03:10:00Z"),
    },
    // 被替代的旧决定：仍保留可读
    {
      id: "dec_alloc_100", project_id: "prj_city", change_id: "chg_007",
      statement: "策划预算按 100 万元口径排布分配。",
      decided_by: "主策",
      instruction_source_version_id: "sv_brief_1",
      rationale: "按客户需求文档口径先行排布。",
      affected_refs: [{ layer: "draft", object_id: "obj_alloc" }],
      supersedes_id: null, created_at: dt("08T03:00:00Z"),
    },
    {
      id: "dec_alloc_60", project_id: "prj_city", change_id: "chg_022",
      statement: "策划预算按 60 万元口径重排分配。",
      decided_by: "主策",
      instruction_source_version_id: "sv_oral_budget_1",
      rationale: "承接「本轮按 60 万推进」的决定，重排投入重点与克制项。",
      affected_refs: [{ layer: "draft", object_id: "obj_alloc", item_id: "alloc_focus" }],
      supersedes_id: "dec_alloc_100", created_at: dt("11T07:45:00Z"),
    },
  ];

  const review_checks = []; // 当前 CLI 尚未提供持久化审核记录。

  const exports = []; // 不用链接冒充成果导出记录。

  /* ══════════════════════ 对象属性目录（23 类 + 内部类型） ═══════════════
     来源：contracts/v0.1/object-types.json 与《Yu+ 对象关系与展示对照表》。
     页面的「对象说明」从这里派生，保证 UI 与 Skill 对同一对象的解释一致。
     ═══════════════════════════════════════════════════════════════════ */

  const THEMES = [
    { key: "background", name: "背景与需求", hue: "blue", types: ["bd_context", "client_brief", "tender_documents", "cooperation_type", "client_history", "client_meetings"] },
    { key: "research", name: "研究与资料", hue: "teal", types: ["venue", "brand_assets", "audience", "competitor_analysis"] },
    { key: "plan", name: "计划与协作", hue: "orange", types: ["milestones", "resources", "responsibilities", "deliverables", "budget_range", "budget_allocation", "project_assessment"] },
    { key: "judgment", name: "判断与决定", hue: "purple", types: ["lead_strategy", "risks", "client_decisions", "project_rating", "assessment_decision", "qa"] },
  ];

  const catalog = [
    { code: "D01", type_key: "bd_context", name: "BD 同步信息", meaning: "项目背景、客户为何现在做、目标与核心问题、决策标准和偏好", boundary: "客户说法、BD 判断与当前采用口径必须分开标示", sources: "BD 口述/文档，D02、D03、D14；缺口关联 D15", usage: "供 R01 主策 Debrief、D17 主策策略引用", missing: "允许未知与不适用；可建议补充，不阻止场景推进。" },
    { code: "D02", type_key: "client_brief", name: "客户原始 Brief", meaning: "原始材料引用、版本，以及从中提取的需求条目", boundary: "用户纠正单独保存，不伪装成客户原文", sources: "客户文件或飞书文档", usage: "R01 与其他 draft 对象的证据", missing: "允许未知与不适用；可建议补充。" },
    { code: "D03", type_key: "tender_documents", name: "招标文件", meaning: "原件引用、版本、范围/交付/评审等要求及差异说明", boundary: "原始招标要求与项目采用的解释分开", sources: "招标原始材料；与 D02、D01 对照", usage: "R01；D09、D10、D18 等", missing: "允许未知与不适用。" },
    { code: "D04", type_key: "venue", name: "场地资料", meaning: "图纸、照片、地址等材料集合，以及有依据的场地条件", boundary: "实测或核实信息与未核实描述必须区分", sources: "本地/飞书材料、可核实公开资料", usage: "D17、D22；R01/R04 按需引用", missing: "允许未知与不适用；未核实尺寸不填成事实。" },
    { code: "D05", type_key: "brand_assets", name: "甲方客户品牌资料", meaning: "品牌材料集合、定位、文化资产、核心信息与视觉规范", boundary: "品牌材料原件与提取结论分开；使用条件关联交付细节", sources: "品牌文件、客户公开资料", usage: "D17；R01/R04 按需引用", missing: "允许未知与不适用。" },
    { code: "D06", type_key: "audience", name: "受众", meaning: "现场观众与传播受众分别记录；画像、需求、触达点及依据", boundary: "现场观众与传播受众分开；AI 假设单独注明", sources: "D01、D02、D14", usage: "R01、D17", missing: "允许未知与不适用。" },
    { code: "D07", type_key: "budget_range", name: "总预算区间", meaning: "客户预算、期望区间、币种及口径；保留不同说法和本轮采用值", boundary: "客户原始预算与本轮采用预算必须并存，不覆盖历史说法", sources: "D01、D02、D03、D14，用户明确决定", usage: "D08、D16、D22；R01/R03 按需引用", missing: "金额未知时不显示为零；币种与口径随金额一并记录。" },
    { code: "D08", type_key: "budget_allocation", name: "策划预算分配", meaning: "投入重点、克制项、分配建议与已采用分配；相关实际审查意见", boundary: "预估、报价、分配建议与已采用分配分开", sources: "D07、D16、D19、D23，用户评审意见", usage: "R03 创意审查结果、D17", missing: "允许未知与不适用。" },
    { code: "D09", type_key: "milestones", name: "时间节点或区间", meaning: "事件、日期/区间、对应交付及 Review 看什么；倒排结果注明依据", boundary: "明确日期与估计区间区分；不重复维护交付规格", sources: "D02、D03、D14、用户安排", usage: "R02 推进要素、R04", missing: "只有事件名也可保存；提供时间需注明类型与时区。" },
    { code: "D10", type_key: "client_decisions", name: "客户关键决策节点", meaning: "客户侧谁决定什么、哪些事项待客户确认、双方决策边界", boundary: "客户决策角色与 D20 内部职责不得混用", sources: "D01、D03、D14", usage: "R01、R04", missing: "允许未知与不适用。" },
    { code: "D11", type_key: "cooperation_type", name: "合作类型", meaning: "竞标、委托、咨询、执行追加等实际类型及说明、依据", boundary: "已确定合作方式与待确认说法区分", sources: "D01、D02、D03", usage: "D16、D17、D18；R01 按需引用", missing: "允许未知与不适用。" },
    { code: "D12", type_key: "competitor_analysis", name: "竞争对手分析", meaning: "已知竞争对象、公开作品、引用材料、分析和判断", boundary: "核实信息与传闻、推测分开标明", sources: "D01、D03、公开资料", usage: "D17；R01/R03 按需引用", missing: "允许未知与不适用。" },
    { code: "D13", type_key: "client_history", name: "客户历史合作方与过往项目", meaning: "历史项目、合作方、作品/媒体、表达特点及来源", boundary: "历史事实与对本次偏好的推断分开", sources: "客户资料、公开记录", usage: "D01、D17", missing: "允许未知与不适用。" },
    { code: "D14", type_key: "client_meetings", name: "与甲方的会议纪要", meaning: "原始纪要/转写、会议时间、客户原话、议题、意见与实际决定", boundary: "原话、摘要、意见与已作决定分开；定位按实际获取能力保存", sources: "飞书或其他真实会议材料", usage: "向多个 draft 对象提供证据", missing: "会议时间未知可缺省；节选需注明采集范围。" },
    { code: "D15", type_key: "qa", name: "客户 Q&A 问题表", meaning: "问题、涉及对象、跟进人、答复、证据、已记录状态", boundary: "无答复与已有答复区分；答复关联到哪些业务对象", sources: "所有对象发现的缺口与用户问题", usage: "R05 展示同一问题表；其他成果引用", missing: "可以只有问题；问题状态是业务事实，不是启动门槛。" },
    { code: "D16", type_key: "project_assessment", name: "立项评估结果", meaning: "档期、资源、供应商、投入及价值匹配判断、依据", boundary: "Agent/用户建议与真实正式评估分开", sources: "D07、D09、D19、D22，用户评估", usage: "D21、D23、D17；R01/R03 按需引用", missing: "允许未知与不适用。" },
    { code: "D17", type_key: "lead_strategy", name: "主策策略", meaning: "本轮目标、策略、调研判断、已有方向候选、取舍理由、实际审查意见", boundary: "已有策略与待讨论建议分开；不要求完成创意方向筛选", sources: "D01、D04—D08、D12、D13、D16、D23", usage: "R03；R01/R04 按需引用", missing: "允许未知与不适用；不要求收集阶段完成创意策划。" },
    { code: "D18", type_key: "deliverables", name: "交付细节", meaning: "轮次、交付物、颗粒度、格式/规格、数量、使用限制、外部依赖、不做范围", boundary: "本轮/某位创作者要求与全项目要求区分；日期统一引用 D09", sources: "D01—D03、D14、用户约定；关联 D05/D19", usage: "R01、R02、R04", missing: "允许未知与不适用；不做范围可单独记录。" },
    { code: "D19", type_key: "resources", name: "内外部资源", meaning: "人员/机构、能力、作品依据、档期条件、参与情况", boundary: "候选、已核实可用、已确认参与必须区分", sources: "团队与合作资料、D01、D16", usage: "D16、D17、R04；D08 按需引用", missing: "允许未知与不适用。" },
    { code: "D20", type_key: "responsibilities", name: "职责边界", meaning: "主策、专业负责人、BD 接口、内部拍板人、任务职责与协作接口", boundary: "建议分工与实际承接分开；不与客户决策角色混用", sources: "用户明确安排、D19、相关会议记录", usage: "R01、R02、R04", missing: "允许未知与不适用。" },
    { code: "D21", type_key: "project_rating", name: "项目评级", meaning: "评级、理由、来源和确认依据", boundary: "建议评级与正式评级分开", sources: "D16、D23、用户明确判断", usage: "资源投入和策略判断；R03 按需引用", missing: "允许未知与不适用。" },
    { code: "D22", type_key: "risks", name: "风险点", meaning: "风险描述、触发条件、影响、应对建议、待核实事项、接受/处理决定", boundary: "风险线索、判断与实际处理决定分开", sources: "各对象与材料，用户判断", usage: "D16、D17、D23；R01—R04 按需引用", missing: "允许未知与不适用。" },
    { code: "D23", type_key: "assessment_decision", name: "评审会结论", meaning: "实际立项评审结论、Go/No-Go、补材料/调整交付/重新评估等决定及行动项", boundary: "立项评审与创意审查分开；是业务记录，不是软件准入门槛", sources: "真实评审记录、用户明确结论", usage: "R04、D17；其他成果按需引用", missing: "允许未知与不适用。" },
  ];

  const internal_types = [
    { type_key: "expression_guide", name: "成果编写要求", meaning: "用户的表达或结构要求：作用于哪份成果、哪些段落、指令来源与版本", boundary: "不是第 24 类业务对象；与事实字段分开，不因改写流程捏造事实变化", sources: "用户口述中的纯表达意见", usage: "绑定某一 review 的段落 ID 或全部段落" },
  ];

  const REVIEW_KINDS = [
    { code: "R01", type_key: "debrief", name: "主策 Debrief", persistable: true, meaning: "客户为何做、要解决什么、面向谁、谁决定什么、本轮交付与边界的完整说明", basis: "D01 背景目标；D02/D03 需求依据；D06 受众；D10 客户决策角色；D20 内部职责；D18 交付边界" },
    { code: "R02", type_key: "advancement", name: "推进要素", persistable: true, meaning: "本轮交付、颗粒度、回收/合稿/Review 节点、相关职责和已有待讨论项", basis: "D09 时间，D18 交付；负责人引用 D20；缺口引用 D15" },
    { code: "R03", type_key: "creative_review", name: "创意审查结果", persistable: true, meaning: "目标、方向、投入重点的实际审查意见、取舍及依据；无正式结论时呈现已有策略与待讨论内容", basis: "D17 主策策略及实际审查意见，D08 预算分配及实际审查意见" },
    { code: "R04", type_key: "creator_brief", name: "内外部创作者 Brief", persistable: true, meaning: "指定创作者/资源和轮次的任务背景、问题、交付要求、日期、职责、协作及使用边界", basis: "D23、D19、D18；背景来自 D01/D06/D17，负责人来自 D20，日期来自 D09" },
    { code: "R05", type_key: "qa_view", name: "客户 Q&A", persistable: false, meaning: "在 review 场景中展示同一份 D15 问题、答复、状态、来源和关联对象", basis: "直接使用 D15，不复制一份独立维护的 review Q&A" },
  ];

  const EPISTEMIC = {
    source_statement: { label: "原文陈述", hue: "blue", hint: "直接来自材料的说法，可回到原文定位" },
    user_supplement: { label: "用户补充", hue: "green", hint: "主策补充的信息，不是客户原文" },
    reported: { label: "转述", hue: "teal", hint: "经他人转述的说法，可能有偏差" },
    hypothesis: { label: "假设", hue: "orange", hint: "尚未确认的判断，不作为事实依据" },
    suggestion: { label: "建议", hue: "purple", hint: "Agent 或用户的建议，不是正式决定" },
    adopted_decision: { label: "采用决定", hue: "indigo", hint: "已采用的口径，附决定依据" },
  };

  const EVIDENCE = {
    quote: { label: "原文引用", hint: "直接引用材料原文" },
    supports: { label: "支持", hint: "该材料支持此条内容" },
    reported: { label: "转述来源", hint: "此条内容源自该材料的转述" },
    instruction: { label: "用户指令", hint: "来自用户的明确指示" },
    contradicts: { label: "相反证据", hint: "该材料与此条说法不一致，需并读" },
  };

  const CHECKS = {
    accepted: { label: "已接受", hue: "green" },
    changes_requested: { label: "提出修改", hue: "orange" },
    noted: { label: "已知悉", hue: "gray" },
  };

  const PROVIDERS = {
    feishu: { label: "飞书", hue: "blue", icon: "doc" },
    local: { label: "本地文件", hue: "teal", icon: "folder" },
    oral: { label: "用户口述", hue: "purple", icon: "mic" },
    web: { label: "网页", hue: "gray", icon: "globe" },
  };

  // 当前能力边界：未进行远端扫描。链接打开本地示例原文，不访问虚构域名。
  for (const source of sources) {
    source.last_checked_at = null;
    delete source.remote_observation;
    if (source.canonical_url) {
      source.demo_original_url = source.canonical_url;
      source.canonical_url = './source.html?id=' + encodeURIComponent(source.id);
    }
  }

  /* ── 派生：让索引在运行时算好 ───────────────────────────────────────── */

  const revById = {};
  object_revisions.forEach((r) => { revById[r.id] = r; });
  const objById = {};
  objects.forEach((o) => { objById[o.id] = o; });
  const svById = {};
  source_versions.forEach((s) => { svById[s.id] = s; });
  const srcById = {};
  sources.forEach((s) => { srcById[s.id] = s; });

  return {
    meta: {
      generated_at: NOW,
      catalog_version: 1,
      data_dir: "~/YuPlusData",
      demo: true,
      note: "示例数据 · 非真实客户材料",
    },
    projects, project_activity, sources, source_versions, captures,
    objects, object_revisions, changes, decisions, review_checks, exports,
    catalog, internal_types, REVIEW_KINDS, THEMES, EPISTEMIC, EVIDENCE, CHECKS, PROVIDERS,
    indexes: { revById, objById, svById, srcById },
  };
})();

export default DATA;
