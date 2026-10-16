# Design QA — Yu+ handoff implementation

Date: 2026-10-16. Browser: Codex in-app browser. Implementation: http://127.0.0.1:7801 .

## Visual truth and evidence

Source: user-supplied `yuplus-handoff.zip`, extracted locally and preserved as `../docs/design/handoff/DESIGN.md` and the three reference PNGs below. Implementation uses the supplied HTML/CSS/data as its foundation, split into files; no new visual concept or image assets were invented.

| State | Source PNG | Implementation PNG | CSS viewport / captured pixels |
| --- | --- | --- | --- |
| Project list | `../docs/design/handoff/01-projects.png` | `../docs/design/qa-2026-10-16/01-projects.png` | 1500 × 1000 / 1500 × 1000 |
| D18 current v2 | `../docs/design/handoff/03-draft-deliverables.png` | `../docs/design/qa-2026-10-16/03-draft-deliverables.png` | 1500 × 1080 / 1500 × 1080 |
| R01 scope paragraph trace | `../docs/design/handoff/05-inspector-trace.png` | `../docs/design/qa-2026-10-16/05-inspector-trace.png` | 1500 × 1120 / 1500 × 1120 |
| R04 creator Brief | Same supplied design language | `../docs/design/qa-2026-10-16/04-review-brief.png` | 1500 × 1080 |
| Narrow materials | Responsive extension, no handoff mobile image | `../docs/design/qa-2026-10-16/mobile-materials.png` | 390 × 844 |

Desktop source and implementation were opened as paired images in the same tool output. Source and final implementation pixel sizes match; browser devicePixelRatio is 1, no density scaling needed. An intermediate D18 capture had an inconsistent size/scroll position and was rejected, then captured again at y=0 and 1500 × 1080. Full-view comparisons are readable at these sizes; object fields, source chip titles and inspector metadata were inspected directly, so additional crop files were not needed.

## Findings and fixes

- [P2, resolved] At 390px the material-page search input extended beyond the viewport (scrollWidth 426px). Fixed the input width inside its flexible container. Post-fix capture `mobile-materials.png` and DOM measurements both show scrollWidth = viewport = 390px; source inspector also stays within 390px.
- [P2, resolved] The supplied fixed body height allowed the navigation sidebar to scroll out of view on long documents. The body now grows with content so the sidebar has a full-height sticky containing block. Final D18 capture retains the reference sidebar/layout.
- [P2, resolved] Supplied draft history buttons did not actually switch content and omitted v1. Now both v1 and current content are readable, with a history badge and return-to-current action. Browser verified the v1 state and return to v2.
- [P2, resolved] Search re-rendered its own focused input. Only content re-renders while typing; verified focus remains in the search box and project filtering returns the two same-name projects.
- [P2, resolved] R05 instance routing did not resolve to the shared D15 view. Verified four questions, answers and the D15 link in the review scene after repair.

## Fidelity surfaces

- **Typography:** retained system/PingFang stack, 38px desktop heading, 19px object heading, 16px/1.78 document text and metadata sizing. Paragraph wrapping and object-field alignment match the reference at equal widths. Minor native text antialiasing differences are expected.
- **Spacing/layout:** retained 268px sidebar, 40px content gutter, card spacing/radii/shadows, directory widths and 400px on-demand inspector. Desktop regions align with the reference. At intermediate narrow widths the directory stacks to protect reading width; at 390px navigation is available through a menu button.
- **Colors/tokens:** uses the supplied tokens.css. Blue/cyan/orange/purple object themes, source chips and epistemic colors retained. Selected D18 is orange; changed review basis is orange.
- **Assets:** the supplied Yu mark and interface symbols are reused from the supplied source. No target asset was replaced. Business media files were not present in the handoff; the mock file preview placeholders remain explicitly limited to the handoff's metadata.
- **Copy/content:** retained main project/example content. Intentional differences: removed invented remote-check, acceptance and export records to honor the existing information spec; displayed “尚无确认记录”; replaced implementation-oriented warning text with a useful Codex update instruction; search placeholders describe their scope and pages without a search implementation omit the input. Corrected two inconsistent Brief evidence references/content. These change small metadata and text heights but preserve the selected design language.

## Interaction verification

In the in-app browser: project search with focus retention; same-name project identities; empty project; draft directory; D18 v2 → v1 → v2; source snapshot inspector and reverse citations; R04 creator instance; R01 paragraph → draft version → original source; R05 same-object view; decisions and superseded decisions; object catalog; narrow-window menu and material inspector. Copy reference was clicked and the clipboard verified to include project ID, object ID and revision ID. Clicking the document title opened a separate tab displaying the local mock original. That temporary tab was closed after verification.

Browser console error/warning logs: empty during tested paths. `npm --prefix frontend test`: four tests passed, including nested fixture identity checks, item-specific changes, missing evidence, and HTTP read-only/path boundaries. Python backend unchanged; its suite was not rerun for this isolated frontend iteration.

## Remaining scope / follow-up polish

Real database/API integration, real Feishu source opening and multimedia playback are not part of this mock preview. Not every deep link at every responsive width has been exhaustively exercised. Metadata density and repeated round/decision labels are inherited from the handoff and can be refined with the user. No actionable P0/P1/P2 visual mismatch remains in the reviewed states.

Implementation checklist: [x] preserve supplied language; [x] primary read-only flows; [x] desktop comparisons; [x] narrow viewport fix/recheck; [x] console checks; [x] independent mock data; [x] preview kept running.

final result: passed

## 用户批注修订：项目列表（2026-10-16）

用户的 12 条页面批注覆盖原始交付图中对应内容。本次移除品牌副标题、项目列表面包屑按钮、标题说明、项目 ID 和归档说明；将搜索与标题放在同一行；项目行增加“复制项目名称”，摘要改为“最新更新”，时间改为基于 `created_at` 的“创建于”；新建提示改为“复制到Agent会话框”并固定在视口底部；目录标题改为“信息收集对象”。项目内部的返回面包屑仍保留。

证据：`../docs/design/qa-2026-10-16/projects-refinement.png`，1499 × 1164。实际标题与搜索中心纵坐标分别约 55.27/55.27px。390 × 844 下未横向溢出；滚动 457px 后底栏底边仍为 832px，最后一行底边 609px 小于底栏顶边 657px，内容可完整滚动到固定区域上方。ResizeObserver 根据底栏实际高度保留滚动空间。

复制按钮鼠标/Enter 操作不触发项目导航；点击第二个按钮后粘贴到搜索框，实际文本为 `YU+ Dev`。搜索保留焦点并能筛选两个同名项目。对象说明新标题在浏览器中可见。浏览器未记录 error/warn。未改动 Skill、CLI 或后端契约。
