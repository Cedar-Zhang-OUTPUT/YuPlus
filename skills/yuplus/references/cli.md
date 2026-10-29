# Yu+ CLI: supported operations

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

## Workspace logo

`logo show`, `logo set`, and `logo reset` operate on the data directory without `--project`. See [appearance.md](appearance.md) only when changing the avatar: image preparation, JSON inputs, version checks and refresh.

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

### Rename a project

When the user asks to rename a project, resolve its existing ID and read `project show` for its current name and `metadata_version`. Then run:

```sh
yu --data-dir DATA_DIR project rename --project PROJECT_ID --name 'New project name' --base-version METADATA_VERSION --request-id REQUEST_ID --json
```

`--base-version` is the integer `metadata_version` just read. The name is trimmed and must not be blank. The response includes `effect`, `project_id`, `name`, `previous_name`, `metadata_version`, `working_scene` and `lifecycle`; the change receipt records both names. Renaming to the current name returns `effect=noop` without changing the metadata version. Retries reuse the same request ID and arguments; a version conflict requires rereading the project, checking the user's intended change and issuing a fresh request ID.

Renaming keeps the project ID, material files, source identities, object revisions, monitoring bindings and history. Do not create a replacement project, move its data directory, or rewrite draft/review just to rename it. Refresh the existing page after success to update the project list, breadcrumb and newly copied references. Existing document text and old copied/exported content retain their historical wording.

### Delete a project

Only for an explicit user request to delete the identified project. Resolve ambiguity before writing, read `project show` for its current name and `metadata_version`, then run:

```sh
yu --data-dir DATA_DIR project delete --project PROJECT_ID --base-version METADATA_VERSION --request-id REQUEST_ID --json
```

Deletion is **soft deletion**, using lifecycle `archived`: the normal CLI list and browser hide it, business writes are blocked, local monitors are paused and active leases are invalidated atomically. Original files, object versions and history remain; this does not free disk space or delete a Feishu group/document. Never recursively remove the shared data directory or object pool. `project list --include-deleted --json` discovers retained projects, and `project show` can inspect one explicitly. For explicit permanent deletion use project purge and the hard-deletion workflow in [deletion.md](deletion.md). Project restore is not available; never edit SQLite.

The response includes `deletion_mode:soft`, `retained_data:true`, new metadata version and `scheduler_actions`. These actions contain the saved monitor/scheduler receipts, not proof that host tasks were stopped. Use the host's native automation tool to pause/remove this project's actual task; if shared with other authorized projects, remove only this project's scope. Reuse the current user's deletion authorization. If host access is unavailable, report the remaining scheduler cleanup; local writes are already blocked. Do not claim complete host shutdown from the local result alone. Retrying an uncertain delete uses the identical request ID and base version; stale metadata must be reread before a fresh request.

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

For monitored group material, follow [chat-materials.md](chat-materials.md): grouped `monitor capture` produces one conversation-segment source; independent attachments/documents use `source.import` through a monitor step with copied local assets. An attachment’s `locator` and draft evidence locators can retain actual sending-message links/identities. Do not paste retrieval keys into business fields.

- `target.mode=create`: provider, resource_type, and remote provider_key/canonical_url when applicable. `target.mode=append`: source_id and actual base_snapshot_id.
- snapshot: title, provider_revision (string or null), captured_at (RFC3339), capture_scope, extraction_profile, provenance, plus body and/or assets. `advance_head` and reason are explicit.
- body holds `{format,text}`. An asset supplies asset_id, role, display_name, mime_type, local_path and storage. Use exact field definitions from the helper. Do not replace actual source text with your project summary.
- Output data.source_id and data.snapshot_id are inputs to subsequent operations. `effect=noop` or snapshot_reused means no new content version; a separate storage-manifest change may create a local snapshot with the same content hash.

### draft.apply

D25 uses `type_key=open_questions`, ordinary draft scope `project`, and the same `draft apply` / `draft show` commands. Read its writable fields with `PYTHON SKILL_DIR/scripts/inspect_contract.py command draft.apply --type open_questions` before writing; do not invent a separate questions command. `options` is a string array; status is `open`, `exploring`, `resolved`, `deferred` or `closed`. These are discussion states, not the D18 answer states. D18 also accepts optional `asked_by` and `answered_by`.

- Top level: reason, objects[], decisions[], and optional instruction_source_version_id.
- Each operation: op_id, type_key, scope_key, base_revision, optionally object_id; set_items/remove_items/title/item_order specify edits. New ordinary draft: scope_key=project and base_revision=null. Existing identity: actual base_revision; do not “create again” to bypass it.
- `set_items` replaces the complete specified item: item_id, data, epistemic_kind, source_refs[], dependencies[]. Preserve unchanged fields/references from its current version. Unmentioned sibling items remain.
- Evidence contains evidence_id, source_version_id, kind, optional locator/asset_id. Dependencies refer to a draft object, revision and stable item ID (`*` only when the whole object is truly required). Within one batch, op_id can refer to a newly produced draft operation.
- D13 schedules: use `time_kind=date` with a date-only `start`, `instant` with an RFC3339 `start` including its actual offset, or `range` with compatible `start/end`. There is no writable `date` field. Dates only embedded in event/note will not enter the Gantt chart. Split distinct calendar occurrences; see the D13 examples in objects.md and inspect `draft.apply --type milestones` before using unfamiliar fields.
- Money uses integer **strings in the smallest currency unit** plus currency: CNY 60 万 = `"60000000"` 分. Never fill unknown amounts with zero.
- Adopted decisions require decision_key, statement, decided_by, instruction_source_version_id, rationale and affected_items with op_id/item_id. Use supersedes_id when replacing a recorded decision. Altering or deleting an adopted item also needs a decision; changing its label to hypothesis is not a shortcut.
- Output objects[].revision_id and meta.change_id supply the new basis/cause; affected_draft_items and affected_reviews show work to inspect next. Do not blindly regenerate all project content.

### Delete and re-enable

`draft delete/restore`, `review delete/restore`, and `source delete/restore` accept JSON through `--input`. Read [deletion.md](deletion.md) for exact scope, causes and restore semantics, then inspect that command's schema. `list --include-deleted` and `show` expose retained identities/history. Removing the last Review block now saves an empty version and soft-deletes the outcome. Draft item removal alone leaves an active empty object.

### review.prepare / review.publish

Before composing, follow [review-structure.md](review-structure.md) for which outputs to generate and their fixed sections. CLI block validation does not enforce that business outline; verify it before and after publishing.

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

For user-authorized Feishu group intake, `monitor` binding, schedule receipts, chronological processing and recovery, read [chat-monitoring.md](chat-monitoring.md). These commands supplement the unchanged four core business contracts. A copied monitor Prompt binds `data_dir`, `project_id`, `monitor_id`, action and viewed configuration version; reread the real binding before executing it. Clicking copy does not run a command.

Use `yu --data-dir DATA_DIR start --json` for managed startup/reuse, `status` to recover the address and `stop` for verified shutdown. `serve --port 0` remains the foreground option. See [operations.md](operations.md). The existing page shows saved source-check results after refresh. Startup scanning does not call AI or rewrite draft/review.

A copied reference/Prompt is navigation context, not a write payload. Bind its data directory, project, object/item/block and viewed revision, then reread the current target. If the user wants synchronization after an existing draft change, reuse the genuine unconsumed draft cause and run prepare/publish; do not invent another draft edit. New facts or wording instructions first update their draft basis. Never overwrite newer content from a stale copied snapshot. Check all affected instances within the requested scope and refresh the browser after successful writes.

## Prepare an internal export evidence snapshot

Use the Python environment in which Yu+ is installed:

```sh
PYTHON -m yuplus.export_bundle --data-dir DATA_DIR --project PROJECT_ID --output OUTPUT_DIR
```

This module reads one consistent saved snapshot and writes `review.md` plus `manifest.json` outside the business data directory. It does not mutate project records or publish remotely. The bundle contains all current Review instances, the same D18 Q&A, cited/current draft versions, provenance, source text and registered asset metadata. Inspect `references_complete`, warnings, missing references, and basis freshness. Resolve incomplete/stale content as authorized, or explicitly preserve and report it; never silently label it synchronized. Asset metadata does not upload media or verify that an external original is still available.

Both files are internal evidence, not publication drafts: never publish the technical text or full provenance appendix verbatim. Follow [export.md](export.md) to author readable Review and hash the final publication draft for the receipt, retaining the fixed manifest's version basis. Later project changes do not change that basis. Local preparation alone is not successful Feishu publication or receipt recording.

## Not implemented in this release

`project context`, project update/archive, diff/history/show helpers beyond those listed, relations queries, review check and GC are not callable. Do not prescribe them as working commands. For today's task use existing show/list/read_basis/history receipts, or honestly state the limitation. Do not treat a user's acceptance as a persisted review-check record until that capability exists.

Installed service management, complete backup/restore and `source check` are available; consult [operations.md](operations.md) only when needed.

## Workspace case libraries

`library add/list/show/update/delete/restore` manages folder/website registrations outside projects. Read [case-library.md](case-library.md) when using these commands. Yu+ stores kind/title/URL and registration metadata only; find folder contents via Feishu CLI and website content via browser/web tools on demand. `delete`/`restore` removes/restores the local registration, never the remote folder or website.

## Feishu export receipts

`export record --project ID --request-id ID --input receipt.json` persists a verified remote export; `export list --project ID` reads the project’s receipts. These commands read/record standalone exports; the current planning-document workflow uses collab bindings and synchronization records instead. Local preparation alone creates no receipt.

## Case research

`research create/update --project P --input FILE --request-id KEY` saves only round metadata and Feishu locators. `research list --project P`, `research show --project P --research ID`, and `research preview --project P --research ID` read rounds / fetch a disposable board preview. Use the explicit data directory. New rounds increment `version`; updates use `base_version = metadata_version` and keep the round/board identity. Read [case-research.md](case-research.md#save-the-research-round) before creating, binding or revising a research board.


## Collaborative planning documents

Use `collab ACTION --project PROJECT_ID --json`. Read [collaboration.md](collaboration.md) for ordered execution and JSON inputs. Read actions: show/pending/schedule. Pull/prepare fetch remote versions and persist inbox/source snapshots; neither rewrites business content. Mutations create/bind/map/push/accept/resolve/pause/resume/scheduler-bind require `--request-id`; commands with payload accept `--input FILE`. `step` wraps the existing source/draft/review contract.

`create` accepts Agent-authored full `xml`, complete `mappings` (inclusive zero-based body block indexes, excluding title), and `expected_local_revisions` for all local keys. It adds no headings. `bind/map` use actual `{start,end}` block IDs and the fetched `base_revision`. Identical ranges may serve multiple local keys; partial overlaps are invalid. A shared-range `push` requires `expected_local_revisions` for every associated key, instead of the single `expected_local_revision`. Existing string heading mappings remain readable. See collaboration.md for creation, readback recovery and direct Feishu document intake.

`accept.handled_keys` lists every remotely changed mapped section returned by comparison (remote/conflict), including ones whose local Review was updated in this operation. An empty array is only appropriate when no mapped section changed. Acceptance rechecks the latest remote snapshot. A changed snapshot requires a new pull.

Use new types `creative_proposals` and `creative_feedback` under draft; `creative_plan` under review with scope `proposal:<existing draft item_id>`. Set `outline_version:2` on every new/reorganized review document. Query schema definitions on demand; display D/R codes are not IDs. User edits and conflict resolution always preserve draft-first causality.
