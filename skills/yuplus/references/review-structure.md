# Planning documents

Read when entering the second scene or organizing/correcting planning documents. Reuse already-read context. Draft is the persistent business layer throughout both scenes.

## Inspect, organize, collaborate

1. Inspect actual relevant draft items and existing outputs, including deliberately deleted identities. Generate every supported output in the requested scope. Dates plus deliverables require advancement; a named request limits scope. Missing information permits a useful partial document, never a gate or invented fact.
2. Use the exact ordered second-level headings below. Write connected content inside them. Unknown sections get a precise short note. Without actual proposals or feedback, leave the corresponding output absent; do not manufacture a scheme or review conclusion.
3. Select real draft items → `review prepare` → `review publish`. Every changed paragraph requires its actual draft cause. Use one stable block per heading or one block containing the whole outline. Set `outline_version:2` on each published document. Preserve unrelated blocks and use the current base revision.
4. Entering the second scene also starts the collaboration workflow: read [collaboration.md](collaboration.md). Save local outputs, create/reuse the project's Feishu collaboration document, and configure an actual host schedule. No separate export prompt or second confirmation is needed within this requested project workflow. A failed remote step must not erase local work.

## Fixed structures

| Output / type | Exact headings, in order | Draft basis |
| --- | --- | --- |
| R01 主策 Debrief / `debrief` | 项目任务; 受众与场景; 主策判断; 本轮创意任务; 边界与判断标准 | D01–D03 task; D09 audience + D07 venue; D19 strategy with D08 brand/D10 competitors/D05 history; D14 deliverables with D13 dates/D16 responsibilities; D08/D11/D12/D13/D14/D19 limits, D17 client decision roles/D16 internal authority. |
| R02 项目推进安排 / `advancement` | 本轮交付与分工; 时间节点与区间; 讨论与评审安排 | D14 deliverables, D16 responsibilities/D15 resources; D13 structured dates (Gantt); D19 criteria, D17/D16 decision roles and existing D21 feedback. Dates belong only in D13, not a second schedule. |
| R03 创意方案 / `creative_plan` | 核心概念; 如何回应项目任务; 叙事与体验; 视觉与案例参考; 深化内容; 待讨论事项 | D20 creative_proposals; supporting task/strategy/audience/materials; D25 open questions or D18 concrete client clarification. Scope `proposal:<draft item_id>`; each direction has a separate stable item and output. |
| R04 创意评审记录 / `creative_review` | 本轮评审对象; 反馈与判断; 取舍与结论; 下一轮修改 | D21 creative_feedback targets the exact original scheme/item/revision; actual decisions update D20/D19 and decision history; resulting work links D14/D16/D13. D24 is project approval assessment, not creative feedback. |
| R05 客户 Q&A / shared `qa` | 客户 Q&A 问题表 | Display the same D18 draft; do not create a duplicate Review. |

R01/R02/R04 use `project` or a real `round:<round_key>` already present in D14. R03 uses `proposal:<item_id>`. Codes are display order; use stable type_key/object_id in commands.

## Creative content

D19 holds insight, strategy and judgment criteria. D20 holds the specific creative direction, its rationale, experience, references and development. Supplementing images or rewriting a scheme revises its existing item; a genuinely different direction creates a new item. Do not synthesize creative proposals merely because the user entered organization.

Distinguish independent directions from iterations, layout studies and historical references using their content and chronology. A separate file or date is not a separate proposal. Preserve prior versions and provenance; if the relationship is uncertain, leave it explicit rather than merging or presenting all material as current alternatives. Correct misclassified saved items through draft before regenerating Review.

Within 深化内容 choose only relevant defined modules: film (`script`, `storyboard`, `key_visual`, `sound`), exhibition (`zones`, `journey`, `exhibits`), interaction (`interaction`), integrated communication (`touchpoints`). Reference images explain what is borrowed. Case research stays independent; bring selected conclusions into project evidence explicitly, never synchronize the whole case library.

## Content responsibilities

- **Debrief:** explain the task, audience, strategic judgment, creative questions and boundaries. 本轮创意任务 describes what the creative work must solve; detailed deliverable inventories, equipment and assignments belong in advancement.
- **Advancement:** maintain delivery, owners, dates and review arrangements. Link the relevant creative judgment instead of repeating the Debrief.
- **Creative plan:** describe this direction. 深化内容 adds concrete development beyond 叙事与体验 and 视觉与案例参考; it must not repeat those sections. 待讨论事项 contains direction-specific questions and effects only. Keep project-wide open issues in D25 and client clarification in D18; refer to them where relevant instead of copying the same list into every plan.
- **Review record:** record actual feedback, decisions and resulting changes against the original target version; do not retell the whole proposal.

Each substantive fact or list has one primary location; other sections add only the relevant implication or a short reference. Preserve meaningful distinctions between rounds. Put a shared reading/permission limitation once, with its scope; repeat only a distinct impact. Required but unsupported sections get one brief note, never filler. Render module keys as natural labels such as 动线、展区、关键视觉, not raw `journey:` or `zones:`. Before publishing, check for duplicated paragraphs, repeated issue tables and misplaced detail across all outputs in scope.

## Corrections

New facts/feedback first update the appropriate draft; expression-only feedback first updates `expression_guide` with instruction evidence. This guide may control wording within the fixed structure. Then publish affected Review using the actual cause IDs. Historical versions keep their original outline; update current legacy outputs only as part of the requested organization/correction, recording that instruction first.

A collaborator's proposal, critique, and formal decision are different. Record attribution only when available; last document editor is not proof of paragraph author or decision authority. Review feedback retains its original target version even after the scheme changes. No decision without real authority/evidence; no date-driven automatic completion.
