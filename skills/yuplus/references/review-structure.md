# Review structure and generation

Read when entering organization, composing Review, or correcting its structure. Reuse once read. This is the fixed content outline, not a completeness gate.

## Inspect, then generate

1. For “enter review / organize the project”, inspect the draft types below and existing Review instances. Reuse current context; query only missing or stale data. Check actual items, not merely object existence. When discovering identities, use `draft/review list --include-deleted` to distinguish absent from deliberately deleted objects; do not use deleted content as current basis. For an explicitly named output, limit work to that output and its affected dependencies.
2. Generate or synchronize every in-scope output whose corresponding draft content is available. Do not stop after R01. In particular, D09 + D18 with content requires R02. Reuse an unchanged, already conforming output instead of publishing another version.
3. If some basis is missing, name the missing object and a useful way to supply it; offer supplementation or organization now with known content. An existing request to organize authorizes partial organization: proceed and mark unknown sections, without asking again. A wholly unsupported output may be omitted with a brief reason; do not fabricate facts, resource identities or review conclusions. An explicit request to sketch an unsupported output can receive the fixed outline as an unsaved preview.
4. Use the exact section names and order below. Write connected content **inside** them; do not add, rename, merge or replace sections with an invented outline. Additional evidence may support the specified content; it does not create extra sections. Missing sections remain “暂无已收集信息” (or a precise known uncertainty).
5. Select real draft items → `review prepare` → `review publish`. Preserve source lineage and actual item/version dependencies. Check the saved outline, all eligible outputs, unknowns and remaining stale dependencies before presenting for user review.

## Fixed outline

Each R object is the parent. The ordered names below are its only second-level sections; use `##` headings in its Markdown. Their explanations describe what to write, not extra headings.

| Parent / type_key | Required sections, in order | Draft basis and meaning |
| --- | --- | --- |
| R01 主策 Debrief / `debrief` | 1. **BD同步信息**; 2. **职责边界**; 3. **受众**; 4. **交付细节** | D01: why the client is acting now and which business/communication problem to solve. D20, with D10 for client decision roles: who decides and their boundaries; keep the two draft identities distinct. D06: on-site and communication audiences. D18: strategy/theme/experience flow/space/content/script/storyboard/technical deliverables, plus exclusions beyond contract, budget, time or required detail. D02/D03 may substantiate these sections, never add chapters. |
| R02 推进要素 / `advancement` | 1. **时间节点或区间**; 2. **交付细节** | D09: dates/ranges, collection, integration and review points, including what each review checks. D18: this round's deliverables and required detail. Reference D20 only where responsibilities explain these elements; do not maintain independent dates/specifications. |
| R03 创意审查结果 / `creative_review` | 1. **主策策略**; 2. **策划预算分配** | D17 and D08 with actual review comments/conclusions. Without actual review, organize known strategy/allocation and label “尚无实际审查结论”; never claim approval or turn AI questions into decisions. |
| R05 客户 Q&A / shared `qa` | **客户 Q&A 问题表** | Display D15 itself, not a new Review document. D24 open questions stay separate. |

R01 must not have additional sections such as “项目任务”, “主题与表达要求”, “预算”, “风险” or “待确认事项”. Relevant information belongs within the four specified sections or its own draft object. A fixed outline does not require filling unknown facts.

## Saving and corrections

For an explicit request to delete a whole output, use [deletion.md](deletion.md); fixed sections do not prevent deleting the output itself. Routine organization does not re-enable a deliberately deleted outcome without user direction.

- Full outputs may use one stable block per section. For a partial output, a single block may contain the complete fixed outline with the union of its real draft dependencies, marking unsupported sections as unknown. Do not cite unrelated items to manufacture a dependency for an empty section. With no actual basis, provide a preview rather than fabricate a publishable object.
- R01–R03 use `project` or an actual `round:<round_key>`. Reuse existing object/block identities where their meaning still matches. A missing identity limits saving that output, not organization of others.
- Factual feedback changes the corresponding draft first. Expression-only or legacy-outline corrections first record the user's instruction in draft `expression_guide`, then prepare/publish with that real cause. Preserve useful content within the fixed sections; remove out-of-outline blocks only in the authorized correction, retaining history. Do not leave old extra chapters appended to the new outline.
- `expression_guide` may govern wording and organization within sections; it cannot authorize an arbitrary replacement of this product outline. Unchanged compliant blocks stay intact. Resolve newly stale dependencies within the target before publishing.
