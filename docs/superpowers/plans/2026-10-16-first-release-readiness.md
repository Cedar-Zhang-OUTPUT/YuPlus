# First Release Readiness Implementation Plan

> Execution: native implementation in the current session, followed by independent code review. The user authorized completing the remaining readiness work; real Agent and cross-machine distribution/upgrade acceptance are explicitly deferred until after release.

**Goal:** Make the existing local application installable, restartable, recoverable and able to detect remote source changes, without redesigning the UI.

**Architecture:** Keep Python standard library, SQLite schema v1 and its existing source observation fields. Maintenance commands own runtime/backup operations; business writes retain the existing transaction boundary. Feishu uses installed lark-cli with explicit user identity and bounded subprocesses. No background AI or autonomous business rewrites.

**Constraints:** Scope narrowed by the user to installation/init/start, backup/restore and Feishu startup checks only. No review/export/media additions. UI styles/layout frozen; no gates on entering draft/review; no credentials stored in Yu+; preserve immutable source/revision history and project isolation. Recovery creates a new destination and never overwrites an existing directory. All writes through CLI; source checks update observations only. Python >=3.12 / SQLite >=3.51.3 remain required.

## Tasks

- [x] Add backup create/verify/restore with SQLite online snapshot, hashed file manifest, registered copied and external assets, failure cleanup and exclusive destinations. Test tampering, WAL data, external relocation and restore conflicts.
- [x] Add start/status/stop and installation entry with runtime preflight, managed service identity, fixed data directory, packaged Skills and explicit Feishu health report. Test reuse, wrong identity, safe stopping, missing runtime and fresh local install.
- [x] Add source check/scan via bounded lark-cli, docx revision comparison, wiki resolution and other-resource metadata markers. Preserve unknown/error semantics, sticky pending updates, import/check race protection and startup background scan. Test unchanged/changed/error/unknown/races; expose via existing UI badges/CLI.
- [x] Sync English/Chinese business and visualization Skills, CLI documentation and acceptance. Run full regression, local install/restore/remote checks and independent review; commit/push after verification. Do not claim post-release user tests completed.

## Review focus

Backup must include external bytes without modifying sealed source records. Concurrent imports/checks must not apply results to the wrong snapshot. Missing authentication and unsupported metadata are never reported as unchanged. Service stop must verify process identity and directory. Authentication failure must not block local browsing.
