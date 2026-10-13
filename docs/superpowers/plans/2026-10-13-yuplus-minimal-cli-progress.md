# Yu+ minimal CLI implementation progress

Plan: 2026-10-13-yuplus-minimal-cli.md

- Implemented Python package and installed `yu` entrypoint, SQLite schema initialization, projects, idempotent transactions and focused queries.
- Implemented three-source capture with local files and immutable snapshots; draft edits and decisions; review preparation and causal publishing.
- Core/draft/source/review and subprocess CLI tests written before implementation; first runs failed on unavailable features. Early integrated suite: 71 tests passed.
- Independent review found adopted-kind bypass, decision pagination dropping same-batch rows, empty review wildcard basis, dangling typed resource references, Feishu identity aliases, storage-policy changes silently reusing external captures, and causal reuse through reverted transitive dependencies. All findings were fixed with reproducing regression tests; post-fix full suite is green.
- Runtime uses installed Python/SQLite (checks SQLite >=3.51.3); this is a development installation, not a standalone bundled binary. No frontend/service/live Feishu scheduler/export/backup/GC installed.
- Project-create request IDs are workspace-global because no project exists yet. Other writes are project-scoped.
- Storage manifest changes create new immutable local snapshots even when remote revision/content hash is unchanged; previous snapshots remain untouched.
- A dangling resource_item_id is rejected with affected locations. The same batch can update/remove those references, then delete the resource. No business completeness gate is added.
- Pagination next_cursor binds command/project plus sequence and record ID; numeric after_cursor remains an explicit incremental history checkpoint.

## Final verification

- ` .venv/bin/python -m unittest discover -s tests -v`: 86 tests passed (real SQLite and CLI subprocesses).
- `.venv/bin/python docs/superpowers/specs/contracts/v0.1/verify_contracts.py`: 94 design-contract checks passed, SQLite 3.53.4.
- `.venv/bin/python scripts/demo_chain.py --cli .venv/bin/yu`: installed CLI completed all 8 demo stages, temporary data removed.
- Independent concurrency smoke: 12 simultaneous project-create requests produced one project and 11 replay receipts.
- Source queries default to metadata; `--include-body` opts into full text. Corrupt SQLite input returns a JSON integrity error and preserves original bytes.
- No frontend or external Feishu writes were performed. Generated persistent demo data is isolated under ignored `.local/acceptance-demo`; real projects were not used.
- Changes remain in the working tree for review; no push, merge or release was performed.
