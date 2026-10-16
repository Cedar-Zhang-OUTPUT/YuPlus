---
name: yuplus-visualization
description: Open and explain the Yu+ project browser, including navigation, saved sources, versions, basis changes, update and Feishu export prompts, and local service problems. Use for Yu+ interface help; business changes belong to the Yu+ project skill.
---

# Yu+ visualization

Help the user read their saved Yu+ project and use its actual controls. The browser is a read-only business view. It can copy references/prompts and reveal registered files; saving project content belongs to the CLI. Navigating a page does not select an Agent's project or change its stored working scene.

## Read only what the task needs

- Opening a project or fixing an unavailable page: [service.md](references/service.md).
- Explaining a page, directory, card, version, or source control: [interface.md](references/interface.md).
- Explaining changed basis, processing an edit reference, or exporting: [review-actions.md](references/review-actions.md).
- An operation fails or its state is unclear: [troubleshooting.md](references/troubleshooting.md).

Reuse guidance already read in this conversation. Refresh stale project data rather than repeatedly loading every skill/reference or the entire project history. For a simple control question, answer it directly; reading all project content is unnecessary.

## Bind the real project

Discover the current address and verify `/api/health`: `mode: "live"`, actual `url`, `port`, and resolved `data_dir`. Verify the project's real ID within that directory. Do not assume port 7801 is production: `npm --prefix frontend run dev` is an explicit demo with sample content, not a database-backed service. Live read failures must not be explained using sample data.

Open the verified address and appropriate hash route using an available browser tool. Preserve other tabs. Locate controls by their visible Chinese label or accessible name, not screenshot coordinates. If no browser control is available, give the verified clickable URL and precise steps; do not claim to have opened or inspected it.

## Keep viewing and writing distinct

- “复制引用”, “复制更新 Prompt”, and “复制飞书导出 Prompt” copy text only. “已复制” does not mean saved, synchronized, or exported.
- Original titles open the stored original address in a new tab when present. “查看引用” opens Yu+'s saved snapshot, possibly historical. A local head snapshot is not proof of remote freshness.
- Resolve requests such as “change this paragraph” from project ID, data directory, object/block/item ID and viewed revision, then reread the current target. Use the installed `yuplus` business skill for the write. If its guidance is already loaded, consult only the relevant reference; do not bounce between full skills recursively.
- New facts or wording instructions go into the appropriate draft basis before `review prepare` and `review publish`. Never write browser view JSON directly to SQLite or submit copied context as a CLI payload.
- Full-project Feishu export prepares local saved content, then uses the available Feishu document skill to create, write, and read back a new document. Report only verified results and real links.

Do not apply the business copilot's end-of-turn project footer to pure Yu+ software development, skill authoring, or unrelated questions. When doing actual project business work, follow the business skill's reporting guidance.

## Maintenance basis

Aligned with the 2026-10-16 frontend integration. Behavioral sources: `frontend/public/app.js`, `data/runtime.js`, `data/review-prompts.js`, `data/basis-diff.js`; service sources: `src/yuplus/gateway.py`, `browser_view.py`, `export_bundle.py`. These are repository-relative implementation locations, not required paths in a standalone skill installation. Check installed CLI help and observed UI when versions differ. Design handoff screenshots are illustrative and do not establish a current browser test or successful external export.
