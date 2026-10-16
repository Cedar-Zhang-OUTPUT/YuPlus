// Shared display vocabulary; no projects or demonstration content.
export const THEMES = [
    { key: "background", name: "背景与需求", hue: "blue", types: ["bd_context", "client_brief", "tender_documents", "cooperation_type", "client_history", "client_meetings"] },
    { key: "research", name: "研究与资料", hue: "teal", types: ["venue", "brand_assets", "audience", "competitor_analysis"] },
    { key: "plan", name: "计划与协作", hue: "orange", types: ["milestones", "resources", "responsibilities", "deliverables", "budget_range", "budget_allocation", "project_assessment"] },
    { key: "judgment", name: "判断与决定", hue: "purple", types: ["lead_strategy", "risks", "client_decisions", "project_rating", "assessment_decision", "qa"] },
  ];

export const REVIEW_KINDS = [
    { code: "R01", type_key: "debrief", name: "主策 Debrief", persistable: true, meaning: "客户为何做、要解决什么、面向谁、谁决定什么、本轮交付与边界的完整说明", basis: "D01 背景目标；D02/D03 需求依据；D06 受众；D10 客户决策角色；D20 内部职责；D18 交付边界" },
    { code: "R02", type_key: "advancement", name: "推进要素", persistable: true, meaning: "本轮交付、颗粒度、回收/合稿/Review 节点、相关职责和已有待讨论项", basis: "D09 时间，D18 交付；负责人引用 D20；缺口引用 D15" },
    { code: "R03", type_key: "creative_review", name: "创意审查结果", persistable: true, meaning: "目标、方向、投入重点的实际审查意见、取舍及依据；无正式结论时呈现已有策略与待讨论内容", basis: "D17 主策策略及实际审查意见，D08 预算分配及实际审查意见" },
    { code: "R04", type_key: "creator_brief", name: "内外部创作者 Brief", persistable: true, meaning: "指定创作者/资源和轮次的任务背景、问题、交付要求、日期、职责、协作及使用边界", basis: "D23、D19、D18；背景来自 D01/D06/D17，负责人来自 D20，日期来自 D09" },
    { code: "R05", type_key: "qa_view", name: "客户 Q&A", persistable: false, meaning: "在 review 场景中展示同一份 D15 问题、答复、状态、来源和关联对象", basis: "直接使用 D15，不复制一份独立维护的 review Q&A" },
  ];

export const EPISTEMIC = {
    source_statement: { label: "原文陈述", hue: "blue", hint: "直接来自材料的说法，可回到原文定位" },
    user_supplied: { label: "用户补充", hue: "green", hint: "主策补充的信息，不是客户原文" },
    reported: { label: "转述", hue: "teal", hint: "经他人转述的说法，可能有偏差" },
    hypothesis: { label: "假设", hue: "orange", hint: "尚未确认的判断，不作为事实依据" },
    suggestion: { label: "建议", hue: "purple", hint: "Agent 或用户的建议，不是正式决定" },
    adopted_decision: { label: "采用决定", hue: "indigo", hint: "已采用的口径，附决定依据" },
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
