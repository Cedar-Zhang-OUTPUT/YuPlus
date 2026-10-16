# Yu+ CLI v0.1: supported operations

Read only the section required by the current operation. In commands below, replace uppercase values with actual values; use returned IDs, never demonstration IDs. Quote local paths. Use a JSON file or stdin, not shell interpolation of client text.

## Discover fields without loading the whole contract

`yu types show --type budget_range --json` returns business meaning and possible sources, **not** all writable JSON fields. The included helper reads the installed application's versioned resources without opening a database:

```sh
PYTHON SKILL_DIR/scripts/inspect_contract.py type budget_range
PYTHON SKILL_DIR/scripts/inspect_contract.py command source.import
PYTHON SKILL_DIR/scripts/inspect_contract.py command draft.apply --type budget_range
PYTHON SKILL_DIR/scripts/inspect_contract.py command review.prepare
PYTHON SKILL_DIR/scripts/inspect_contract.py command review.publish
```

Use the Python environment in which Yu+ is installed (in its repository this is `.venv/bin/python`). `SKILL_DIR` is the actual installed skill directory. `draft.apply --type TYPE` narrows the reference to that type; for a multi-type batch inspect only the additional types you will write. The helper does not validate your payload or execute a command. If the installed package lacks these resources, stop guessing and inspect its actual version/help.

## Project and reads

```sh
yu --data-dir DATA_DIR project create --name 'Project name' --request-id REQUEST_ID --json
yu --data-dir DATA_DIR project list --json
yu --data-dir DATA_DIR project show --project PROJECT_ID --json
yu --data-dir DATA_DIR source list --project PROJECT_ID --json
yu --data-dir DATA_DIR source show --project PROJECT_ID --source SOURCE_ID --json
yu --data-dir DATA_DIR source show --project PROJECT_ID --source SOURCE_ID --snapshot SNAPSHOT_ID --include-body --json
yu --data-dir DATA_DIR draft list --project PROJECT_ID --json
yu --data-dir DATA_DIR draft show --project PROJECT_ID --object OBJECT_ID --json
yu --data-dir DATA_DIR review show --project PROJECT_ID --object OBJECT_ID --json
yu --data-dir DATA_DIR changes list --project PROJECT_ID --limit 20 --after-cursor CURSOR --json
yu --data-dir DATA_DIR decisions list --project PROJECT_ID --limit 20 --json
```

`draft/review show --revision REVISION_ID` retrieves an old version; `review list` discovers review identities and scope_key (currently omitted by review show); reuse a known scope or read this list when needed. Omit `--after-cursor` on the first history page. Its returned `next_cursor` is an opaque next-page token bound to the query and project. A numeric cursor means “strictly after this known change sequence”. Do not advance to `meta.history_cursor` while unread pages remain. If you already know the objects relevant to the request, read them directly rather than walking history from the beginning.

`source show` returns metadata by default; `--include-body` explicitly requests body text. It has no field-selection or block-range flag. `draft show` returns a whole object, not just a selected item. Use the smallest existing object/source query and reuse it.

## Four core JSON commands

```sh
yu --data-dir DATA_DIR source import --project PROJECT_ID --request-id REQUEST_ID --input source.json --json
yu --data-dir DATA_DIR draft apply --project PROJECT_ID --request-id REQUEST_ID --input draft.json --json
yu --data-dir DATA_DIR review prepare --project PROJECT_ID --input prepare.json --json
yu --data-dir DATA_DIR review publish --project PROJECT_ID --request-id REQUEST_ID --input review.json --json
```

All core inputs contain `api_version:"1"` and the matching dotted `command`. Writes need a unique request ID; `review prepare` is read-only. Unknown business fields are not required, but valid IDs, types, evidence and concurrency inputs are technical requirements.

### source.import

- `target.mode=create`: provider, resource_type, and remote provider_key/canonical_url when applicable. `target.mode=append`: source_id and actual base_snapshot_id.
- snapshot: title, provider_revision (string or null), captured_at (RFC3339), capture_scope, extraction_profile, provenance, plus body and/or assets. `advance_head` and reason are explicit.
- body holds `{format,text}`. An asset supplies asset_id, role, display_name, mime_type, local_path and storage. Use exact field definitions from the helper. Do not replace actual source text with your project summary.
- Output data.source_id and data.snapshot_id are inputs to subsequent operations. `effect=noop` or snapshot_reused means no new content version; a separate storage-manifest change may create a local snapshot with the same content hash.

### draft.apply

- Top level: reason, objects[], decisions[], and optional instruction_source_version_id.
- Each operation: op_id, type_key, scope_key, base_revision, optionally object_id; set_items/remove_items/title/item_order specify edits. New ordinary draft: scope_key=project and base_revision=null. Existing identity: actual base_revision; do not “create again” to bypass it.
- `set_items` replaces the complete specified item: item_id, data, epistemic_kind, source_refs[], dependencies[]. Preserve unchanged fields/references from its current version. Unmentioned sibling items remain.
- Evidence contains evidence_id, source_version_id, kind, optional locator/asset_id. Dependencies refer to a draft object, revision and stable item ID (`*` only when the whole object is truly required). Within one batch, op_id can refer to a newly produced draft operation.
- Money uses integer **strings in the smallest currency unit** plus currency: CNY 60 万 = `"60000000"` 分. Never fill unknown amounts with zero.
- Adopted decisions require decision_key, statement, decided_by, instruction_source_version_id, rationale and affected_items with op_id/item_id. Use supersedes_id when replacing a recorded decision. Altering or deleting an adopted item also needs a decision; changing its label to hypothesis is not a shortcut.
- Output objects[].revision_id and meta.change_id supply the new basis/cause; affected_draft_items and affected_reviews show work to inspect next. Do not blindly regenerate all project content.

### review.prepare / review.publish

Prepare input: target (type_key/scope_key, known object_id), cause_change_ids[], select_basis[{object_id,item_ids}]. Existing outputs bring their dependencies automatically; initial output needs actual selected draft items. Prepare returns real read_basis and affected blocks, not AI-written content. For a new expression guide, affected_blocks/affected_reviews may be empty because no existing dependency is stale; use available_causes[].eligible_blocks to identify the requested rewrite scope. Empty stale-impact lists do not cancel the user’s instruction.

Publish input: reason, documents[]. Each document supplies target, base_revision, read_basis, structure_cause_change_ids[], plus set_blocks/remove_blocks/title/block_order as needed. set_blocks has block_id, markdown, dependencies[], cause_change_ids[]. Preserve stable IDs. The CLI stores a complete reconstructed document.

For existing review, a relevant draft change is required for every actual edit. Source-import changes are not review causes. For pure title/order changes use a guide targeting `*` and an appropriate intent; a saved block rewrite can target specific blocks. Each block tracks its own consumed causes. `DRAFT_BASIS_CHANGED` requires rereading/regenerating, not a forced write.

Expression-guide sequence: record the instruction source → draft.apply with type_key=expression_guide, scope_key=`review:OBJECT_ID`, item data `{review_object_id,block_ids,instruction,intent}`, instruction evidence → review.prepare → review.publish referencing that new change and including the guide in read_basis. Intent is rewrite/structure/omit/retain. Preserve business dependencies; a wording guide does not substantiate factual claims.

## Results and recovery

- Check the process exit code and `ok`; do not infer success from having invoked a command. Success data describes the actual result. meta.replayed means an old receipt, not fresh current project state.
- Retry an uncertain submission with the **same** request ID and identical payload. For revised payloads use a **new** request ID. A safe replay precedes file rereading, so do not import again under a new identity after a timeout.
- SOURCE_EXISTS/SOURCE_DUPLICATE: inspect the returned identity/candidate, then reuse or append. Do not change a provider key merely to evade duplication.
- BASE_REVISION_CONFLICT/DRAFT_BASIS_CHANGED: refresh affected versions, reconcile the intended edit, retry with a new payload/key. Do not rewrite stale fields over newer work.
- DRAFT_CHANGE_REQUIRED/CAUSE_ALREADY_APPLIED: identify the real missing cause. Reuse a preview without saving or record the genuinely new user instruction in draft; never fabricate a change.
- A failed batch commits no partial object changes. A successful earlier draft stays saved when a later review fails; report that distinction and continue the remaining authorized work.
- Stop retrying when the same unresolved error recurs; explain the concrete missing permission, material or environment requirement instead of looping or bypassing the CLI.

## Local browser and copied references

`yu --data-dir DATA_DIR serve --port 0 --json` runs a foreground loopback-only gateway and reports its actual address. Reuse a healthy service only when `/api/health` reports `mode: live` and the intended absolute `data_dir`; another directory or the Node demo is not interchangeable. Port 0 allocates a free port. Keep the managed session alive; do not kill an existing listener to claim its port. The separate `yuplus-visualization` Skill explains actual routes and controls. CLI writes appear after “刷新页面” or browser reload; they are not live-pushed.

A copied reference/Prompt is navigation context, not a write payload. Bind its data directory, project, object/item/block and viewed revision, then reread the current target. If the user wants synchronization after an existing draft change, reuse the genuine unconsumed draft cause and run prepare/publish; do not invent another draft edit. New facts or wording instructions first update their draft basis. Never overwrite newer content from a stale copied snapshot. Check all affected instances within the requested scope and refresh the browser after successful writes.

## Prepare a complete local export

Use the Python environment in which Yu+ is installed:

```sh
PYTHON -m yuplus.export_bundle --data-dir DATA_DIR --project PROJECT_ID --output OUTPUT_DIR
```

This module reads one consistent saved snapshot and writes `review.md` plus `manifest.json` outside the business data directory. It does not mutate project records or publish remotely. The bundle contains all current Review instances, the same D15 Q&A, cited/current draft versions, provenance, source text and registered asset metadata. Inspect `references_complete`, warnings, missing references, and basis freshness. Resolve incomplete/stale content as authorized, or explicitly preserve and report it; never silently label it synchronized. Asset metadata does not upload media or verify that an external original is still available.

Use the manifest's version IDs and hashes for remote readback. A later project change does not change this fixed export snapshot. A prepared bundle is not a successful Feishu export or a persisted export-history record. Follow the materials reference for external publication.

## Not implemented in this release

`source check`, `project context`, project update/archive, diff/history/show helpers beyond those listed, relations queries, review check, exports, backup/GC are not callable. Do not prescribe them as working commands. For today's task use existing show/list/read_basis/history receipts, or honestly state the limitation. Do not treat a user's acceptance as a persisted review-check record until that capability exists.
