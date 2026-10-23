# Find cases

Use for a project’s 找案例 research, new rounds and changes to an existing board. This workflow can start from user text, files or available project context; completing draft/review is not a prerequisite. Do not create sources or modify draft/review merely to conduct research.

## Choose the research identity

- The submitted **开启一轮新的找案例研究** prompt starts a new round: v1 initially, then v2, v3… Each round has its own board locator; preserve previous rounds. Copying the prompt or viewing history alone does nothing. Do not derive the next version from the currently viewed historical version.
- Adding cases/images, revising explanations, regrouping or refining the current direction updates the same round and board. Direct user edits in Feishu are also same-version changes. Read the latest target board before editing and preserve the user’s edits; never overwrite from a stale local draft.
- Continuing an interrupted run or retrying a write resumes that run and reuses its resource identities. Check uncertain outcomes before creating another document/board. An explicit new-round request creates a new round; a selected historical board does not change that intent. Ask briefly only when the target round or new-versus-update intent is genuinely unclear.
- A specified board is usable when compatible with the requested round. Do not reuse a previous round’s board as the new version’s content; resolve that conflict before writing.

## Understand this request

Reuse known project identity and context. Read only inputs relevant to choosing cases: purpose, audiences, brand, creative intent, experience, technical role, deliverables and constraints. User-supplied criteria, client preferences and exploration directions apply to this research only; do not build a lasting preference profile or carry them into another round without instruction.

OUTPUT’s aesthetic guidance comes from the user-imported case libraries. Read that evidence when available; do not independently construct a company-wide aesthetic profile or mine unrelated historical projects/chats for one. If guidance is missing, describe the limits of the fit judgment and work from the current request.

Distinguish confirmed facts, reasonable inferences and open questions; distinguish client statements, individual opinions, lead-planner judgments and formal decisions. Keep material conflicts explicit. Ask together about gaps that materially change the search direction; other gaps do not block research. Derive short working selection criteria and reference purposes (concept, visual, experience mechanism, production/technology); no mandatory form or approval gate.

## Search and assess

Read [case-library.md](case-library.md) when accessing registered sources. Obtain active libraries using `library list` and their details as needed. Unless the user narrows the scope, **make a direction-relevant search in every registered website and Feishu shared folder**. Missing types need no substitute. This is targeted coverage, not exhaustive crawling. Report inaccessible/unsearched libraries separately from searched libraries with no useful matches.

Use browser/web tools for websites and the installed Feishu Skills/CLI for folders and selected documents. Check relevant subfolders and pagination within the bounded search. No built-in studio whitelist or mandatory site list: the user’s registrations are the library sources. Also actively explore relevant public sources, including GitHub where useful; public search need not wait for library failure. Do not silently register discovered sites as new libraries.

Read the specific case page/document, not just a search snippet or homepage. Match each visual to its actual case; split multi-case pages into the right sections. Exclude placeholders, duplicate responsive images, generic site background media and unrelated recommendations. Follow authorized access; if login is required, have the user complete it in the site. An access failure is not evidence that no cases exist.

For each selected case, explain its actual design idea, supported OUTPUT fit, fit to this request, concrete reusable aspects, reference limits and next action. Tie reasons to images, mechanisms or evidence. Partial relevance is allowed when scoped. Distinguish the original work from proposed adaptations. Only label AI use, tools, responsibilities or results when supported; an uploader is not automatically a project owner. Separate reference studios, comparable cases and evidenced competitors. Do not infer this bid’s competitor proposal, budget, schedule or effectiveness from public imagery. Compare and combine cases when useful without forced pairing or quotas.

## Capture visuals and preserve evidence

A clear **screenshot is sufficient** for basic visual reference; original-image/video downloads are optional enhancements, never prerequisites. Wait for real content to load, choose representative views or video frames, capture and inspect clarity/cropping/obstructions. Label original image, page screenshot or video frame accurately. Do not generate substitute case imagery. Use available browser capture tools; a failed capture method does not prove the site is unusable.

Keep temporary downloads outside Yu+ business data and backups. Organize selected material as `source_case-original-name`; preserve original download filenames, use descriptive screenshot names, and retain filename/source mappings. Never mirror the entire site or folder.

Save selected assets and the detailed evidence index **in Feishu**, at the user’s destination or an available default destination without moving original materials. Keep exact case/source names, source URLs, access dates, image mappings, video positions, evidence locations, supported personnel/tool details and concise search coverage in the index. Keep research-only preferences in current working context; no separate persistent or cross-project preference archive. Report what was actually saved, with usable links; conversation memory is not a saved index.

Yu+ retains only research-version metadata and document/board locators. It does not store case bodies, assets or the evidence index. The local service’s disposable preview cache stays outside business storage/backup. Ordinary preview refresh never invokes the Agent or changes research version numbers.

## Compose, verify and iterate

Read installed `lark-doc` authoring/whiteboard guidance and `lark-whiteboard` when creating or changing the board; load only the needed references, reuse already-read instructions. Put actual case images into the board, not merely image URLs. Use proportional images, short text, clear hierarchy and spacing; keep text beside its images.

Board outline:
1. **How we selected cases:** brief project criteria, supported OUTPUT guidance and necessary uncertainties; a few representative images where useful.
2. **External references / Internal references:** within each, group by actual selection reasons such as concept, visual language, spatial experience, interaction, AI or production. Use only applicable groups, prioritize strongest matches and tag multiple reasons without duplicating cards.
3. **Recommended directions and next steps:** combinations and useful validation actions, without treating research as a finalized creative proposal.

Each case card: **original name | source → key images → design idea → OUTPUT fit → project fit → reusable aspects / limits → next action → original link**. Keep detailed provenance, operational logs, personnel lists and resource keys in the Feishu index, not across the board.

Read back the actual board and inspect its rendered preview: images loaded, text readable, grouping correct, links point to the intended case and user edits survived. Link the selected research version to its verified board URL/locator. Report research coverage, saved material/index, board completion and unresolved items separately; do not claim completion for failed uploads or unverified rendering.

Use feedback to improve the current research and its explanations. Do not infer acceptance from silence, generalize a one-off preference into company policy or claim to have fully learned OUTPUT’s aesthetic. End with relevant choices such as supplementing criteria, refining this round or explicitly starting another; do not steer this workflow automatically into draft/review.

## Save the research round

Use installed `yu` with the explicit `--data-dir` and `--project`. Read `research list` / `research show --research ID` only when needed to identify or resume a round. All writes use `--input FILE --request-id KEY`; retry the same logical write with the same payload/key. Never write SQLite directly.

1. **New research:** `research create` with `{"api_version":"1","command":"research.create","title":"Research title"}`. Save returned `id`, `version` and `metadata_version`. It reserves the round, not a completed board. A retry reuses this receipt, not a new request. Use the research ID in the Feishu document/index so an uncertain create can be recovered before retrying.
2. **Create and bind:** use `lark-doc` to create the document and its board, or append a new board to the chosen destination. Read back the returned document URL, whiteboard block ID and board token. Immediately `research update` with the locator payload below; use an actual document anchor for the board. A round’s board identity is fixed after binding, and cannot belong to another round. Resume this board after a partial failure; do not create a replacement silently.
3. **Fill or revise:** read current board nodes/preview first, upload images to that board with `docs +media-upload --parent-type whiteboard --parent-node BOARD_TOKEN`, then use `lark-whiteboard` to write the actual images and content. Reuse each remote write’s `--idempotent-token` on retry. Preserve user edits; prefer targeted/append changes. Never use blanket overwrite as a routine update. If a remote outcome is uncertain, read it back before trying again.
4. **Record success:** after verifying remote content and rendered preview, `research show`, then `research update` with `research_id` and its current `base_version` (`metadata_version`). Omit the locator fields when unchanged. This advances only metadata/update time; it does not allocate v2. Failed remote writes do not get a success update. A local version conflict requires re-reading and reconciling, not blindly retrying writes.
5. **Verify display:** `research preview --research ID` checks the same read-only export/cache path used by the page. Open the project’s `/case-finding` page, verify the selected vN and “打开飞书画板” link. Refresh the page after binding/creating a round to reload history. Routine preview fetching is automatic and never calls the Agent.

Initial locator input for `research update` (substitute returned identities):
```json
{"api_version":"1","command":"research.update","research_id":"research_ID","base_version":1,"document_url":"https://tenant.feishu.cn/docx/DOC","board_url":"https://tenant.feishu.cn/docx/DOC#BLOCK_ID","board_token":"BOARD_TOKEN"}
```

`version` is the research round number; `metadata_version` is the local optimistic-write counter. `created_at` / `updated_at` describe saved research metadata, while `fetched_at` describes a preview fetch. User edits in Feishu remain in the same round and appear on automatic refresh without changing these local business timestamps. These are independent research rounds, not immutable snapshots of every Feishu edit.

If installed help lacks these commands, report the installed-version gap; do not claim the demo is saved research or recreate existing remote work to retry local registration.
