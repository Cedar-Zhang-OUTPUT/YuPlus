# Yu+ Minimal CLI Implementation Plan

> **For agentic workers:** Execute the approved minimal chain task by task using TDD; independent source and review modules can be delegated with the interfaces below.

**Goal:** Run project creation, source import, draft editing and causally constrained review publishing locally through `yu`.

**Architecture:** Python package with one SQLite database and content-addressed local files. A common command runner owns schema validation, idempotency and short transactions; domain modules implement sources, drafts and reviews. No frontend or model runtime.

**Tech Stack:** Python >=3.12; bundled/runtime SQLite >=3.51.3 checked on startup; jsonschema 4.25.1 with date/URI validation; standard-library unittest.

**Spec:** ../specs/2026-10-13-yuplus-data-cli-contract.md and contracts/v0.1/.

## Global Constraints

- 23 draft types, four persisted review types; R05 is D15 view.
- Explicit project context, immutable snapshots/revisions, request idempotency, base-version concurrency checks.
- No information-completeness or stage gates; no Agent processing status.
- Source ingestion receives Agent-read content and local files. Real Feishu fetching/check scheduling, browser gateway, exports, backup and GC are outside this minimal chain.
- Source changes do not edit draft; review changes require relevant, unconsumed draft changes including expression guidance.
- Preserve supplied design documents. This is the first implementation in an empty repository; work in current checkout on a codex/ feature branch, no need to manufacture a base commit from unrelated untracked files.

## Shared module interfaces

`yuplus/core.py` provides:
- `YuError(code, message, *, details=None, retryable=False, next_action='')`.
- `canonical(value)->str`, `digest(value)->str`, `new_id(prefix)->str`, `now()->str`, `insert(db, table, **values)`.
- `Context(db, data_dir:Path, project_id:str, change_id:str)` with attributes `changed_refs:list[dict]`, `causal_change_ids:list[str]`; SQLite db uses Row factory.
- `get_object(db, project_id, object_id)->dict` verifies project membership and returns row; `load_revision(db, project_id, revision_id)->dict` returns row with decoded `payload`, `lineage`, and maps `sources` and `dependencies` keyed by item/block ID. Source refs use input names; dependency refs use input names plus `fingerprint`.
- `fingerprint(db, project_id, revision_id, item_id)->str` handles `*`; includes saved selected data/evidence/dependency fingerprints, excludes containing version ID.
- `is_fresh(db, project_id, revision_id, item_id, seen=None)->bool` checks current selector equivalence and recursive dependencies.
- `resolve_dependency(ctx, dep)->dict` checks current effective draft basis, same-project/selector existence and returns input-shaped dep plus server fingerprint.
- `write_revision(ctx, object_id, payload, *, sources=None, dependencies=None, lineage=None, changed_items=None)->dict` saves+seals+advances head and adds changed_ref `{object_id, before_revision_id, revision_id, item_ids}`. Returns `{object_id, revision_id, version}`. Caller checks noop before invoking.

`source.py`: `prepare_import(data_dir, request)->dict` stages/copies blobs outside transaction after replay precheck; `import_source(ctx, request, prepared)->dict` returns command data and populates changed_refs. `show_source(db,pid,sid,snapshot_id=None)->dict`.
`draft.py`: `apply_draft(ctx, request)->dict`.
`review.py`: `prepare_review(ctx, request)->dict` read-only; `publish_review(ctx, request)->dict`.
`app.py`: `App(data_dir).execute(command, payload=None, *, project_id=None, request_id=None)->dict` handles envelopes/transactions; raises YuError on domain failure, CLI formats it. `close()` closes connection.

## Review Focus

- Replay after caller's file was removed returns original result without rereading it (source task).
- Stale draft base inside a multi-object batch rolls back all objects (draft task).
- An unrelated sibling draft item should not invalidate an unchanged review block (core/review tasks).
- An old cause already reflected by an initial review cannot authorize rewriting it (review task).
- Invalid/missing parameters or malformed JSON still produce machine-readable CLI errors (integration task).

### Task 1: Runtime, projects and common transactions

Files: pyproject.toml, yu, src/yuplus/{__init__,__main__,cli,app,core}.py, src/yuplus/contracts/*, tests/test_core.py.
- [x] Write project persistence/isolation, replay/conflict and runtime/schema tests; run and observe missing implementation failure.
- [x] Implement package, installable `yu` entrypoint, runtime check, WAL/FKs/recursive triggers and atomic initialization; project create/list/show; shared interfaces.
- [x] Run `python -m unittest tests.test_core -v` and package smoke checks.

### Task 2: Source ingestion

Files: src/yuplus/source.py, tests/test_source.py.
- [x] Test oral/Feishu metadata/local copy inputs, source append/noop/conflict, selection capture, file hash failure and replay after removal.
- [x] Implement source identity, immutable capture, streamed file copy and dedup, repeat capture and base snapshot checks.
- [x] Run `python -m unittest tests.test_source -v` and report results.

### Task 3: Draft editing and provenance

Files: src/yuplus/draft.py, tests/test_draft.py.
- [x] Test approved budget example, source/decision requirements, multi-project rejection, stale batch rollback, stable item order, expression guides and dependency cycles.
- [x] Implement all 23 type validation from approved schema plus money/time/relationship checks; atomic full-item changes and immutable decisions.
- [x] Run `python -m unittest tests.test_draft -v`.

### Task 4: Review preparation and causal update

Files: src/yuplus/review.py, tests/test_review.py.
- [x] Test initial generation, update after draft, direct rewrite rejection, consumed cause rejection, stale basis, expression guide, independent blocks and retained tombstones.
- [x] Implement read-only prepare, whole-result assembly and atomic publish; block-level causal lineage, current/transitive dependency checks.
- [x] Run `python -m unittest tests.test_review -v`.

### Task 5: End-to-end usability and review

Files: tests/test_cli.py, scripts/demo_chain.py, README.md, docs/superpowers/plans/2026-10-13-yuplus-minimal-cli-progress.md.
- [x] Execute CLI subprocess tests including invalid JSON and source → draft → review with generated IDs.
- [x] Supply install/run instructions and a disposable full-chain demo; add focused queries for source/draft/review/history/decisions and types.
- [x] Run full `python -m unittest discover -s tests -v`, original contract verification and installed CLI demo.
- [x] Fresh independent review; fix consequential findings with regression tests; record tested limits.
