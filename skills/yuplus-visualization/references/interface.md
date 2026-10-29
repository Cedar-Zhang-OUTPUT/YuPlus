# Page and control guide

Use visible Chinese labels in user instructions. The desktop view has left navigation, a reading area, and an on-demand detail inspector. Smaller windows collapse navigation and rearrange content; use the explicit navigation/directory buttons on touch devices instead of relying on hover.

## Projects and navigation

The project list supports search and empty states. Open the intended project by identity, especially when names match. “新建项目” offers text to copy into the Agent conversation; it is not a browser database-creation form. The Agent creates a requested project through the business CLI. Two templates support supplying files or monitoring a designated Feishu group. Their inline fields prepare clipboard text only; blank fields copy as `______`. Users attach files in the Agent conversation. Copying alone does not create a project or schedule monitoring.

Project navigation contains “项目信息”, “策划文档”, “原始资料”, and “修改与确认记录”; the object definitions page explains supported types. The navigation toggle expands/collapses the sidebar. Its footer reports page refresh time and offers “刷新页面”. That timestamp is not a remote-source check time. The history page presents stored changes and decisions, not an audit approval or export created merely by clicking a button.

The “信息分类说明” page opens from the question-mark button beside “项目信息”, not a dock entry. Timeline `owners` may be empty, one name or several names; saved names appear in smaller gray text after the Gantt event title. Q&A shows “提问人” and “回答方” separately; unknown values show “未明确”. Follow-up ownership does not establish either identity.

## Information collection: draft

The reading area groups the 23 business object types. They are available categories, not 23 mandatory completed records. “全部 23 类” / “只看有内容” switches the directory filter. Clicking a directory entry scrolls to its object; scrolling updates the selected entry.

The “信息目录” is initially collapsed. Hover opens a floating preview without resizing the reading layout. Moving away or choosing an entry closes that preview. Clicking “展开信息目录” or “固定展开信息目录” pins it open and changes the layout; choosing entries then leaves it open. “收起信息目录” collapses it. In a narrow window expansion appears downward. The click controls are also the touch/keyboard route.

Cards show version and update time. Use “历史版本” to open the draft version menu, then select “历史版本 v…” or “当前版本 v…”. Arrow Up/Down and Home/End move among menu options; Enter/Space activates a focused button; Escape closes the menu. History selection changes what is read, not the saved current version. Historical cards show a notice and a way back to current.

Long text is folded after three lines where the text block supports folding. Click/tap the text, or focus it and press Enter/Space, to expand or collapse. Short text and blocks containing interactive elements may not be foldable. Text selection does not toggle it. Folding is recalculated for the available width.

Hover or keyboard-focus a colored item card to expose the vertical information-nature label, such as “原文信息”, “策划补充”, “建议方向”, or “当前采用”. This explains the saved epistemic kind; it is not a status change or a separate edit control. The expanding color edge does not change the text width.

Structured money is displayed from integer smallest-unit amounts and currency; recognized amounts in prose are highlighted red. Highlighting is a display heuristic, not validation or a reason to edit source wording/insert HTML. Unknown amounts stay unknown.

The D09 Gantt chart reads saved structured start/end values, not dates embedded in prose. Every concrete calendar point or complete interval belongs in this chart; separate noncontiguous occurrences into separate D09 items. TBC/proposed dates remain chartable with their qualification and evidence. Only undated explanations stay as prose cards. If a dated item is missing, inspect and correct its D09 fields through the business Skill/CLI, then refresh; do not patch UI data or invent dates. Timelines accept both day and minute precision, point events and ranges. Do not invent midnight or a timezone for a day-only value. Expand a milestone for its detail card. Delivery timelines organize rounds and reference time nodes; a reference date is not automatically a confirmed deadline.

Q&A cards show both question and answer. Missing answers remain pending; an inapplicable answer retains its explanation. Source evidence appears in the shared “依据” row.

D24 “开放性问题” appears under “判断与决定”, with question, context, impact, options, discussion status, conclusion, evidence and related objects when recorded. Its states are 待讨论 / 探索中 / 已有结论 / 暂缓 / 已关闭. It is separate from client clarification Q&A; R01–R03 may cite it, while R05 still shows only D15.

## Monitored groups in draft and review

Project rows show “监控 N 个群” and a count needing attention. The shared “项目群更新” card appears in both “项目信息” and “策划文档”, scoped to that project; an older server without monitor data shows an empty state. A verified stored group AppLink opens in a new tab. The page does not configure the group by opening it.

Each group shows its configured interval, enabled/paused/pending schedule state, collection of **all accessible history**, “已拉取至”, “最近检查”, “最近同步完成”, “最近保存结果”, pending messages and saved errors. When present, “已记录澄清消息” counts historical clarification dispositions, not currently unanswered D15 questions. Collection complete means the fetched history window is complete, not that every message was adopted or that inaccessible history was read. Check time can record a failed attempt; use the error and completion result together.

“已保存调度绑定回执” reflects the saved host receipt. A stale receipt is “调度状态待核验”; an overdue result says “尚未收到本轮结果”. Neither proves an Agent is currently running. Do not invent live reading/progress statuses. “查看已保存运行记录” expands only records supplied by the service; “拉取未完成” / “处理未完成” / “已完成” describe saved stages. If no records are available, use the inspection指令 rather than claiming there were no runs.

“复制立即同步指令”, “复制暂停指令” / “复制恢复指令”, “复制调整间隔指令”, “复制解除绑定指令”, and “复制查看记录指令” copy an intent bound to the real data directory, project, monitor and configuration version. They make no business or scheduler changes. Send the desired copied request to the Agent conversation to execute it; interval changes need the requested minute value. Recheck current configuration before a write. After completion refresh the page to see saved results.

## Review outputs

| Code | Visible output | Identity rule |
| --- | --- | --- |
| R01 | 主策 Debrief | Saved review object |
| R02 | 项目推进安排 | Saved review object |
| R03 | 创意评审记录 | Saved review object |
| R05 | 客户 Q&A | View of the same D15 draft Q&A, not another persisted review copy |

Select the type and, where applicable, the round. Review versions are available through the version area and its “查看” buttons; historical reading is labelled. Paragraph actions are “完整追溯路径” and “复制引用”; changed paragraphs additionally have yellow “查看差异”. The orange changed-basis banner offers “查看受影响段落” and “复制更新指令”. The title's “复制生成飞书文档指令” covers the entire project, regardless of the selected card. See [review-actions.md](review-actions.md) for scope and execution.

## Original, snapshot, and actual file

“依据” lines separate two actions. Clicking the saved source title opens its canonical original URL in a new tab when one is available. For a local source, the title opens the unique available original file from the cited snapshot in a new tab; when no unique original can be identified, it opens that snapshot’s details. “查看引用” opens the saved snapshot actually referenced by that card. Never equate opening an original with importing its latest version.

“来源详情” contains source identity/URL, saved remote-check information, saved snapshot versions, the selected snapshot's body and files, and reverse references. Choose a snapshot's “查看” to inspect its saved contents. “本地主快照” means the local selected head, not confirmed remote latest. Snapshot text may be complete, a declared selection, or absent with only assets available. Reverse references list current draft items using this source across its snapshots; they are not a complete inventory of every historical reference. Follow historical review lineage to inspect its exact old evidence.

Available registered image files can appear as previews; supported audio/video use browser controls. “打开文件” opens an available asset in a new tab. PDF rendering, playback/codecs and saving/downloading depend on the browser and format; unsupported formats may download. “下载” saves available file-pool attachments using their recorded original filenames, including attachments to spoken input and files relocated into the pool during restore. The download contains the saved file bytes, not a new export of extracted text. Do not describe an icon/metadata as a rendered PDF. Text/Markdown snapshot display is not a full-fidelity office-document viewer.

“在 Finder 中显示” appears only when the macOS service confirms an available registered external original at its unchanged path. Internal hash-named copies and restored pool files offer “下载” instead. On other platforms, available files also use download. Selection depends on asset storage and availability, not the source provider (local, oral or Feishu). It never reveals an internal pool blob as though it were the original. Requests use project, snapshot and asset IDs; the service resolves the path. Never suggest passing arbitrary paths or shell commands through the reveal endpoint. Missing, changed or unavailable files do not erase their provenance records. Demo placeholders must not be presented as real downloadable or revealable originals.

## Case library sources

“案例库” under Browse opens `#/libraries`: workspace-wide Feishu folder and website cards with type, clickable title and saved time. Titles open the original source in a new tab; cards hide full URLs. The bottom “新增案例库” panel has two independent input/prompt rows: Feishu shared folder and website. Each requires a valid link before copying; a website accepts HTTP(S), while the folder row retains Feishu validation. Copying only prepares a request. Follow the business Skill’s `case-library.md` and CLI, then refresh. Removal prompts target the library ID and remove only the local registration; restore preserves its type. Contents remain remote: Feishu CLI reads folders, browser/web tools read websites on demand. This view does not display or claim to have read their contents.

## Workspace avatar
Hover, focus or click the top-left avatar to reveal **更改头像**. It copies an instruction scoped to the current data directory; attach an image in Codex and follow the Yu+ appearance reference. The browser does not upload or write images. Refresh after the CLI change. Escape closes the menu.

## Find cases

Under the current project, 案例分析 opens its independent research view. History lists v1/v2 and creation/update times to the second. The **复制开始分析指令** explicitly requests a **new research round**; copying does not create one. Additions, explanation edits and direct Feishu edits stay in the current round. Follow the business Skill’s case-research.md; this is not a draft/review write.

To the left of refresh, **打开飞书画板 ↗** opens the selected version’s verified board link in a new tab, retaining its anchor (document link fallback). A missing link disables the entry. Switching versions switches the target; do not invent a link from a sample image. Preview refresh is the local program’s responsibility. The CLI saves real research rounds; the local service exports the visible board every 60 seconds. Hidden pages stop polling; errors retain the last image, and authentication/permission failures pause polling. Demo versions remain explicitly illustrative. New or newly bound rounds require a page refresh to reload history.
