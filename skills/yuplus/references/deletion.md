# Delete items, objects and sources

Read for an explicit deletion or re-enabling request. Use the current project and real versions; deletion is not part of routine collection, organization or upgrading. All deletions retain history and files. Never edit SQLite or remove the shared file pool.

## Choose the right scope

| Request | CLI mutation |
| --- | --- |
| Rewrite draft items | `draft apply`: `set_items` replaces the whole specified item, including evidence/dependencies; preserve siblings. |
| Delete draft items | `draft apply`: `remove_items` lists actual item IDs. Removing all items leaves an active empty object. |
| Delete a whole draft object | `draft delete`: removes its current items through the same decision/reference checks, then hides the object. |
| Rewrite/remove Review blocks | `review publish`: `set_blocks` / `remove_blocks`, after real draft changes. Removing the last block saves an empty version and automatically hides the Review. |
| Delete a whole Review | `review delete`: removes all current blocks with real draft causes, then hides the Review. |
| Remove a material from the library | `source delete`: hides the source and stops its remote checks; existing citations and original bytes remain readable. This does not retract facts in draft. |
| Re-enable a deleted object/source | `draft restore`, `review restore`, `source restore`. Source content returns unchanged; draft/Review reopens its **empty current version**, not old business content. Read an old version and reapply requested content through the normal causal workflow when needed. |

`draft/review/source list --include-deleted` discovers retained identities; normal lists hide them. `show` still reads their current or historical versions and reports `archived_at`. Restore the existing identity before reusing that type/scope or source; do not create duplicates to bypass history.

## Inputs and execution

These six commands use `--project PROJECT_ID --request-id REQUEST_ID --input FILE --json`, like other JSON writes. Inspect only the needed contract with `PYTHON SKILL_DIR/scripts/inspect_contract.py command draft.delete` (substitute the command).

Every input has `api_version:"1"`, matching `command`, and a meaningful `reason`:

- Object delete/restore: `object_id`, `base_revision` from current `show`.
- Source delete/restore: `source_id`, `base_snapshot_id` from `source show.head_snapshot_id`.
- `draft delete`: optional `decisions` and `instruction_source_version_id`. Deleting adopted decisions **requires** decision records: point each affected item to the internal `op_id:"delete"`, retain the real user instruction and supersession history. If D19 resources remain named by deliverables/responsibilities, correct those references first (or remove the affected items together with `draft apply`), then delete the empty object. A failed command leaves it intact.
- `review delete`: `read_basis` from `review prepare` and `cause_change_ids` covering every removed block. For an instruction to delete the whole output, save the user's instruction source, update its draft `expression_guide` targeting `*` with intent `omit`, then prepare and delete. A source-import receipt alone is not a cause.

Example source deletion input:

```json
{"api_version":"1","command":"source.delete","source_id":"ACTUAL_SOURCE_ID","base_snapshot_id":"ACTUAL_SNAPSHOT_ID","reason":"用户要求移出材料库"}
```

Check the receipt, current visibility, retained historical version and returned `affected_draft_items` / `affected_reviews` or `referenced_by`. Follow actual impacts within the user's request: a draft deletion can authorize removal of dependent Review blocks; source hiding alone does not invalidate or rewrite their factual content. Do not cascade-delete other objects. Publish empty Review deletions even if an old round identity no longer exists; valid causes and exact target identity are still required.

On re-enabling an empty Review, explicitly select the actual draft items again in `review prepare`, and record any new expression instruction before republishing; the old deletion cause cannot be reused. Reusing unchanged IDs does not reset consumed causes. Refresh the browser after successful writes; deleted records disappear from active lists, while historical citations remain accessible. No permanent purge is available.
