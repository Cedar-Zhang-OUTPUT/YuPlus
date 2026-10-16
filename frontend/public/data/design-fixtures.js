/* Fictional UI fixtures for all previously empty business object types.
   These records are only loaded by the standalone preview, never by the CLI. */
export const DESIGN_FIXTURES = [
  {
    key: 'tender', objectId: 'obj_tender', title: '招标文件', provider: 'feishu',
    sourceTitle: '城市记忆展厅｜采购文件与澄清记录（模拟）',
    body: '【采购概况】项目采用邀请比选，采购文件 V2 于 2026-10-03 发布。原始总预算上限为 100 万元，含客户自行采购的设备。\n【原始范围】主影片成片 1 支（约 8 分钟）及 3 面展墙图文；原始目标为 2027 年春季开馆。\n【评审方式】创意与叙事 40 分、团队履历 25 分、报价 25 分、进度保障 10 分。提交叙事方案、预算拆分、团队履历和进度表。\n【澄清记录】10 月 13 日主策确认，本轮执行按 60 万元、交付概念脚本与展墙排版稿；原始采购要求保留，正式变更附件尚待客户回签。\n【投递】2026-10-23 17:00 截止，通过客户指定工作群提交 PDF，签章纸质版后补。',
    items: [
      { id:'tender_overview', kind:'source_statement', data:{topic:'采购方式与文件版本', procurement_method:'邀请比选', document_version:'V2 · 2026-10-03', scope:'主影片与展墙图文内容策划', raw:'原始上限 100 万元，含设备采购', related_object_ids:['obj_budget','obj_coop']} },
      { id:'tender_scoring', kind:'source_statement', data:{topic:'评审标准', criteria:['创意与叙事 40 分','团队履历 25 分','报价 25 分','进度保障 10 分'], required_materials:['叙事方案','预算拆分','团队履历','进度表']} },
      { id:'tender_submission', kind:'source_statement', data:{topic:'投递要求', submission_at:'2026-10-23 17:00', format:'PDF 电子版；签章纸质版后补', channel:'客户指定项目工作群', requirement:'材料需明确首轮工作范围、报价口径和授权费用。'} },
      { id:'tender_clarification', kind:'user_supplement', extraSource:'sv_oral_scope_1', data:{topic:'原始要求与本轮解释', text:'原文件要求成片，本轮采用概念脚本；原始要求保留供对照，正式变更附件尚待客户回签。', related_object_ids:['obj_deliv','obj_budget'], follow_up:'BD 跟进客户回签'} },
    ],
  },
  {
    key:'competitor', objectId:'obj_competitor', title:'竞争对手分析', provider:'web',
    sourceTitle:'同类展陈团队｜作品观察与访谈摘录（模拟）',
    body:'以下团队与作品均为虚构模拟样本。\n【远山叙事工作室】公开作品《街巷回声》使用口述史访谈、老照片与轻量动画；团队擅长纪实叙事。公开案例页未披露报价或本次参选情况。\n【流光展陈设计】作品《港口的一天》以空间声场、多屏装置和感应交互为主。客户转述该团队可能参与比选，尚无正式名单。\n【观察判断】当前项目可用“城市生活的日常细节”形成叙事区别，但这属于策划建议，不代表已经赢得客户偏好。\n【待核实】两家团队是否参选、报价区间、核心团队档期。',
    items:[
      {id:'competitor_yuanshan',kind:'source_statement',data:{topic:'远山叙事工作室',name:'远山叙事工作室（模拟）',works:'《街巷回声》',capability:'口述史访谈、档案影像整理、轻量动画',evidence_status:'已收录公开案例；参选情况未知',text:'公开作品重视人物叙述与地方记忆，适合低设备依赖的常设展内容。'}},
      {id:'competitor_liuguang',kind:'reported',data:{topic:'流光展陈设计',name:'流光展陈设计（模拟）',works:'《港口的一天》',capability:'空间声场、多屏装置、感应交互',evidence_status:'客户转述可能参选，未取得正式名单',text:'技术展示更突出；尚无本次报价、档期或核心人员资料。'}},
      {id:'competitor_difference',kind:'suggestion',data:{topic:'差异化切入建议',text:'以居民日常和可核实的口述史细节组织叙事，优先保证内容完整性，不把设备规模当作核心卖点。',related_object_ids:['obj_strategy','obj_audience']}},
      {id:'competitor_unknown',kind:'hypothesis',noSource:true,data:{topic:'竞争态势待核实',text:'既有合作团队可能具有现场协作优势，但不据此推断客户已经倾向某一方案。',to_verify:'正式参选名单、团队投入与报价区间'}},
    ],
  },
  {
    key:'history',objectId:'obj_history',title:'客户历史合作方与过往项目',provider:'web',
    sourceTitle:'文旅局｜过往内容项目回顾（模拟）',
    body:'【2024 城市记忆影像季】合作方为河岸影像社，发布 6 支人物短片，主要呈现老城居民与手艺人的日常。客户公开回顾强调“人物表达真实”。\n【2025 滨江文化步道导览】合作方为拾页设计，产出地图、12 块导览牌及线上导览页面。项目后期增加双语信息，排版修改较多。\n【合作经验】BD 复盘称，文旅局习惯先审内容框架，再组织跨科室核对名称、史实与版权；此项属于内部经验转述。\n【本次推断】可以提前准备史实核验清单与授权台账，但历史经验不能直接视为本次已确认流程。',
    items:[
      {id:'history_film',kind:'source_statement',data:{topic:'2024 · 城市记忆影像季',project_name:'城市记忆影像季',partner:'河岸影像社（模拟）',period:'2024 年',deliverable:'人物短片 6 支',expression:'纪实人物访谈与日常场景',feedback:'客户公开回顾强调“人物表达真实”'}},
      {id:'history_wayfinding',kind:'source_statement',data:{topic:'2025 · 滨江文化步道导览',project_name:'滨江文化步道导览',partner:'拾页设计（模拟）',period:'2025 年',deliverable:'地图、12 块导览牌与线上导览页面',feedback:'后期新增双语信息，版式经历多轮调整'}},
      {id:'history_experience',kind:'reported',data:{topic:'过去的协作节奏',text:'BD 复盘认为，客户通常先看框架，再由多个科室核对史实、名称与版权；本次审批顺序仍需另行确认。',related_object_ids:['obj_clientdec','obj_qa']}},
      {id:'history_inference',kind:'suggestion',data:{topic:'对本次工作的参考',text:'提前建立史实核验清单和授权台账，并将双语需求是否存在列入客户问答。',related_object_ids:['obj_strategy','obj_risks']}},
    ],
  },
  {
    key:'assess',objectId:'obj_assess',title:'立项评估结果',provider:'feishu',
    sourceTitle:'首期内容项目｜内部评估工作底稿（模拟）',
    body:'【档期】概念脚本定稿参考区间为 2027-01-05 至 01-18；含一次内部评审及一轮集中反馈。口述史素材未齐时，先提交结构稿。\n【资源】周叙已确认参与导演工作；视觉设计人选仍在确认。先完成脚本与图文排版，避免同时投入拍摄、后期与装置制作。\n【预算】本轮按 60 万元执行；设备由客户自行采购，档案授权另按实际用量控制。\n【价值与风险】项目具备公共文化内容样本价值，但需要明确授权边界与客户回签。当前底稿为评估建议，不等于评审会的正式结论。',
    items:[
      {id:'assess_schedule',kind:'suggestion',data:{topic:'档期可行性',assessment:'可推进，有前置条件',rationale:'先结构稿、后素材补全，避免等待全部访谈结束',condition:'口述史素材包须明确交接批次',related_object_ids:['obj_timeline','obj_risks']}},
      {id:'assess_resources',kind:'suggestion',data:{topic:'资源与供应商匹配',assessment:'导演资源已有，视觉设计待确认',capacity:'主策 1 人、导演 1 人、视觉设计 1 人',gap:'视觉设计档期与授权采购接口',related_object_ids:['obj_resources','obj_resp']}},
      {id:'assess_budget',kind:'suggestion',extraSource:'sv_oral_budget_1',data:{topic:'投入与预算匹配',assessment:'建议按 60 万元的本轮工作范围安排投入',min_minor:60000000,max_minor:60000000,currency:'CNY',scope:'概念脚本、展墙排版、素材整理；不含成片和设备',related_object_ids:['obj_budget','obj_alloc']}},
      {id:'assess_value',kind:'suggestion',data:{topic:'价值与关键风险',assessment:'建议作为重点跟进项目',rationale:'可形成公共文化内容样本，但投入需受边界约束',condition:'客户回签本轮范围；授权费用设上限',related_object_ids:['obj_rating','obj_decision']}},
    ],
  },
  {
    key:'rating',objectId:'obj_rating',title:'项目评级',provider:'feishu',
    sourceTitle:'城市记忆展厅｜评级与资源投入记录（模拟）',
    body:'【初步建议】评估工作组建议 A 级，理由是公共文化示范价值、长期内容资产积累与团队能力匹配。\n【采用评级】2026-10-16 主策采用 B+ 级“重点跟进、分阶段投入”。原因是本轮预算已收敛、客户变更回签未完成，暂不按完整制作项目投入。\n【投入边界】先配置策划、导演与视觉设计；拍摄和后期制作排期在下一轮范围确认后再安排。\n【复核条件】授权费用明显超出预留、客户新增成片要求，或素材交接延期两周时，重新评估评级。',
    items:[
      {id:'rating_proposed',kind:'suggestion',data:{topic:'初步建议评级',rating:'A · 优先投入（建议）',rationale:'公共文化样本价值高，团队经验与题材匹配',scope:'评估工作组建议，未作为资源承诺',related_object_ids:['obj_assess']}},
      {id:'rating_adopted',kind:'adopted_decision',data:{topic:'当前采用评级',rating:'B+ · 重点跟进、分阶段投入',decided_by:'主策',rationale:'本轮预算收敛，客户范围回签尚未完成；先投入内容策划',effective_at:'2026-10-16 11:00',related_object_ids:['obj_decision','obj_budget']}},
      {id:'rating_resource_policy',kind:'adopted_decision',data:{topic:'评级对应的投入方式',text:'先配置策划、导演与视觉设计；拍摄、后期与成片制作人员在下一轮范围确认后再安排。',decided_by:'主策',related_object_ids:['obj_resources','obj_deliv']}},
      {id:'rating_recheck',kind:'user_supplement',data:{topic:'重新评估条件',trigger:'授权费用超预留、客户新增成片要求，或素材延期两周',follow_up:'主策组织复核，BD 补充客户确认材料',related_object_ids:['obj_risks']}},
    ],
  },
  {
    key:'decision',objectId:'obj_decision',title:'评审会结论',provider:'feishu',
    sourceTitle:'10 月 16 日｜内部立项评审纪要（模拟）',
    body:'【会议】2026-10-16 10:00–11:00，主策、BD 与制作统筹参加内部立项评审。\n【结论】Go：按现有第一轮范围继续推进。采用 B+ 项目评级，预算按 60 万元安排。该结论是业务记录，不构成页面功能的准入门槛。\n【范围决定】本轮仅交概念脚本与展墙排版稿；成片顺延至下一轮，设备采购与展陈施工不包含在内。\n【行动项一】BD 于 2026-10-20 18:00 前取得客户对本轮范围的书面确认。\n【行动项二】主策于 2026-10-22 前整理访谈名单与授权缺口，视觉设计负责人确认档期。\n【复核】若客户坚持本轮成片或新增拍摄工作，单独评估预算与交期，不自动追加工作。',
    items:[
      {id:'decision_go',kind:'adopted_decision',data:{topic:'立项评审结论',decision:'Go · 按第一轮范围继续推进',meeting_at:'2026-10-16 10:00–11:00',participants:['主策','BD','制作统筹'],decided_by:'主策',rationale:'先完成内容策划，按阶段安排制作投入',related_object_ids:['obj_assess','obj_rating']}},
      {id:'decision_scope',kind:'adopted_decision',extraSource:'sv_oral_scope_1',data:{topic:'本轮范围与预算',text:'采用 60 万元本轮口径，只交概念脚本与展墙排版稿；成片顺延，设备采购和展陈施工不在本轮。',decided_by:'主策',related_object_ids:['obj_budget','obj_deliv']}},
      {id:'decision_action_client',kind:'adopted_decision',data:{topic:'行动项 · 客户范围确认',action:'取得客户书面回签',owner:'BD',due_at:'2026-10-20 18:00',progress:'进行中',related_object_ids:['obj_tender','obj_qa']}},
      {id:'decision_action_material',kind:'adopted_decision',data:{topic:'行动项 · 素材与资源确认',action:'整理访谈名单、授权缺口并确认视觉设计档期',owner:'主策 / 制作统筹',due_at:'2026-10-22',progress:'待开始',related_object_ids:['obj_resources','obj_risks']}},
      {id:'decision_reassess',kind:'adopted_decision',data:{topic:'范围变化后的处理',trigger:'客户坚持本轮成片或新增拍摄',decision:'重新评估预算与交期，完成确认后再安排投入',decided_by:'主策'}},
    ],
  },
];
