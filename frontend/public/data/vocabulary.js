// Shared display vocabulary; no projects or demonstration content.
export const THEMES = [
    { key: "background", name: "背景与需求", hue: "blue", types: ["bd_context", "client_brief", "tender_documents", "cooperation_type", "client_history", "client_meetings"] },
    { key: "research", name: "研究与资料", hue: "teal", types: ["venue", "brand_assets", "audience", "competitor_analysis"] },
    { key: "plan", name: "计划与协作", hue: "orange", types: ["milestones", "resources", "responsibilities", "deliverables", "budget_range", "budget_allocation"] },
    { key: "judgment", name: "判断与决定", hue: "purple", types: ["lead_strategy", "risks", "client_decisions", "project_rating", "assessment_decision", "qa", "open_questions", "creative_proposals", "creative_feedback"] },
  ];

export const REVIEW_KINDS = [
    { code: "R01", type_key: "debrief", name: "主策 Debrief", persistable: true, meaning: "客户为何做、要解决什么、面向谁、谁决定什么、本轮交付与边界的完整说明", basis: "D01 背景目标；D02/D03 需求依据；D09 受众；D17 客户决策角色；D16 内部职责；D14 交付边界" },
    { code: "R02", type_key: "advancement", name: "项目推进安排", persistable: true, meaning: "本轮交付、颗粒度、回收/合稿/Review 节点、相关职责和已有待讨论项", basis: "D13 时间，D14 交付；负责人引用 D16；客户澄清引用 D18，开放议题引用 D25" },
    { code: "R03", type_key: "creative_plan", name: "创意方案", persistable: true, meaning: "具体方向、体验叙事、参考与深化内容", basis: "D20 方案；关联任务、策略、受众和资料；D25 待讨论议题" },
    { code: "R04", type_key: "creative_review", name: "创意评审记录", persistable: true, meaning: "针对具体方案及版本的反馈、取舍与下一轮修改", basis: "D21 创意评审与反馈；D20 方案；修改任务关联 D14/D16/D13" },
    { code: "R05", type_key: "qa_view", name: "客户 Q&A", persistable: false, meaning: "在 review 场景中展示同一份 D18 问题、答复、状态、来源和关联对象", basis: "直接使用 D18，不复制一份独立维护的 review Q&A" },
  ];

export const EPISTEMIC = {
    source_statement: { label: "原文信息", hue: "blue", hint: "直接来自材料的说法，可回到原文定位" },
    user_supplied: { label: "策划补充", hue: "green", hint: "主策补充的信息，不是客户原文" },
    reported: { label: "转述信息", hue: "teal", hint: "经他人转述的说法，可能有偏差" },
    hypothesis: { label: "待验证判断", hue: "orange", hint: "尚未确认的判断，不作为事实依据" },
    suggestion: { label: "建议方向", hue: "purple", hint: "Agent 或用户的建议，不是正式决定" },
    adopted_decision: { label: "当前采用", hue: "indigo", hint: "当前采用的方向，保留决定者与依据；不等同于客户确认" },
  };

export const EVIDENCE = {
    quote: { label: "原文引用", hint: "直接引用材料原文" },
    supports: { label: "支持", hint: "该材料支持此条内容" },
    reported: { label: "转述来源", hint: "此条内容源自该材料的转述" },
    instruction: { label: "用户指令", hint: "来自用户的明确指示" },
    contradicts: { label: "相反证据", hint: "该材料与此条说法不一致，需并读" },
  };

export const CHECKS = {
    accepted: { label: "已接受", hue: "green" },
    changes_requested: { label: "提出修改", hue: "orange" },
    noted: { label: "已知悉", hue: "gray" },
  };

export const PROVIDERS = {
    feishu: { label: "飞书", hue: "blue", icon: "doc" },
    local: { label: "本地文件", hue: "teal", icon: "folder" },
    oral: { label: "用户口述", hue: "purple", icon: "mic" },
    web: { label: "网页", hue: "gray", icon: "globe" },
  };
