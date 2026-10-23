# Read changes, request updates, and export

## Trace and difference semantics

“完整追溯路径” follows the displayed review paragraph to its cited draft revision/item and original saved source snapshots. The “前往” action can open the draft's current page; verify or select its cited old version when investigating history. Historical reading must retain the historical revision, never substitute current facts into its lineage.

Orange warnings concern actual referenced items (and their dependencies), not every change to the containing draft object. Revision numbers alone do not establish an affected paragraph. Use the saved comparison state for explanation; use a fresh CLI `review prepare` for a write decision. A matching saved basis is not a guarantee of remote-source freshness or user approval.

“查看差异” compares “当前成果采用的依据” with “最新版本的依据”. Old changed values use red minus signs, new values green plus signs. The cards include fields, information nature and per-version sources; unchanged entries can be expanded. Where multiple cited bases changed, choose which basis to inspect. For an indirect change, the same inspector follows saved dependency edges to the changed upstream item and identifies its path; trace includes its historical source. Whole-object references also compare title and item order.

If the original referenced item was deleted and several items were added, describe the removal and additions in that object separately. Similar titles do not prove replacements or a one-to-one mapping. A missing old/current revision or missing evidence means “unknown / 无法比较”, not added, deleted, unchanged or synchronized. Check the actual stored versions; do not convert unknown into a green success claim. A historical review's lineage and copied reference refer to the displayed historical version, while the update/export Prompts target current saved outputs.

## User asks to change the page content

“复制引用” carries project identity, the object/item/paragraph and viewed version with readable labels. Exact fields depend on the control/version. Read what is actually copied; do not invent an absent ID or infer it from a title alone. Bind any missing data directory through the healthy service and verify identities through CLI reads.

The live “复制更新 Prompt” concerns the selected review object. It carries a compact context: project ID/name, actual data directory, capture time, current object/revision IDs, block-level basis hints and missing-evidence identifiers. It is not a full source export or a CLI input payload. The page has only copied it; the user sends the Prompt to the Agent to request execution.

Use the installed business `yuplus` skill, consulting its `references/review-structure.md` fixed outline and relevant CLI guidance on demand (reuse once read):

1. Reread the current target, actual old/current draft items and necessary sources from that data directory. A copied Prompt may be stale; preserve concurrent edits.
2. If the user supplied new facts or expression/structure requirements, capture the instruction and update the relevant business draft or scoped expression guide first. If existing draft changes already justify synchronization, use those actual causes.
3. Run `review prepare`, author the affected content with the returned real basis/causes, then `review publish`. Preserve stable IDs and unaffected content; resolve conflicts by rereading instead of forced writes. Do not invent a cause to authorize a rewrite.
4. Verify saved versions and remaining affected state, refresh the browser, and report what changed and what remains unresolved. A successful draft followed by a failed review is a partial result, not rollback of the draft or a completed update.

Pure UI viewing does not require a business write. A preview-only request stays a preview. If the installed business skill is unavailable, inspect actual CLI help/contracts and explain the limitation rather than fabricate commands.

## Whole-project Feishu export

The copy button supplies a short project-scoped request with `project_id` and `data_dir`; it does not embed content or version history. For execution, read the installed business `yuplus` Skill's `references/export.md` (reuse once read). That reference owns preparation, complete Feishu writing/readback and `export record/list`; do not duplicate the workflow here.

The adjacent history icon opens saved export receipts for this project in the inspector, newest first. Each entry shows export time and a document title linking to Feishu in a new tab. It remains available for every Review category, including empty ones. No records means no persisted receipts, not proof that no document was ever created. Viewing history and copying a Prompt perform no write/export.

## Deleted content

Current lists and export roots exclude soft-deleted objects/sources. Historical records remain available for provenance; a source drawer marks a deleted source while keeping its original files readable. An old Review route keeps the category shell with an empty state. User-requested deletion/re-enabling uses the business Skill’s `references/deletion.md` and CLI, not browser writes; an empty restored draft/Review is not automatic restoration of old content.
