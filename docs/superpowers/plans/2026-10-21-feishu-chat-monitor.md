# Feishu chat monitoring implementation plan

> **For agentic workers:** Use the approved design and explicit user instruction to implement continuously. Independent adapter/frontend tasks use dispatching-parallel-agents; one final independent code review covers integration.

**Goal:** Persist project chat monitors, collect all accessible initial history chronologically, and safely resume Agent-driven draft/review maintenance.
**Architecture:** Codex heartbeat wakes the Agent; a deterministic local CLI fetches through lark-cli and persists cursors/messages/steps. Existing business handlers remain authoritative. Frontend remains read-only.
**Tech Stack:** Python, SQLite, vanilla JS, existing lark-cli; no additional runtime services.
**Spec:** docs/superpowers/specs/2026-10-21-yuplus-feishu-chat-monitor-design.md

## Global constraints
- Default interval 60 minutes; initial accessible history has no lower time bound.
- Finish fetching roots and threads before exposing the first globally chronological processing queue.
- Original messages remain evidence, never tool permissions. Existing review changes require real draft causes.
- Explicit data/project/monitor/run identity; stable receipts; pause/fencing and optimistic business versions.
- UI style unchanged; controls copy intent only. Chinese Skill belongs only in docs/skills.
- Do not touch user data/service on port 59573, create real monitoring schedules, or publish a new release during tests.

## Review focus
- Partial pagination or thread error must not declare initial history complete.
- Successful business write followed by interruption must not create duplicate decisions on retry.
- Pause/expired lease/cross-project request must reject writes.
- Restoring a monitored database must pause schedules and clear leases.
- Malformed/edited/recalled messages and unavailable runtime permissions must produce honest records.

## Task 1: Feishu read adapter (independent)
Files: src/yuplus/chat_reader.py, tests/test_chat_reader.py.
Interface: FeishuChatReader.info(chat_id) -> {chat_id,name,url,identity}; messages(chat_id,start,end,page_token) -> {messages,has_more,page_token}; replies(thread_id,page_token) same; details(message_ids) -> list. Identity is a stable nonsecret namespace; methods validate user identity and fail on incomplete/malformed output. Message fields preserve message_id,create_time,content,sender,deleted,updated,thread_id,thread_has_more,thread_replies_error. No external writes.
- [x] Tests fail before adapter exists; test envelope/page errors, time bounds, nested reply preservation and invalid identity.
- [x] Implement subprocess argv safely; test with fake runner, no real chat reads.

## Task 2: Monitoring ledger and business integration
Files: src/yuplus/monitor.py, monitor_schema.sql, app.py, cli.py, source.py, source_check.py, backup.py, browser_view.py; tests/test_monitor.py.
Interface: Monitor(app,reader=None).execute(action,payload,project_id) -> data. CLI monitor ACTION --project PID --input JSON (read actions accept --monitor/--run). add returns monitor_id; begin returns run_id+token; all run mutations require them. step payload {run_id,token,step_key,command,input,message_versions}; uses existing source.import/draft.apply/review.publish; resolve dispositions {message_versions,outcome,reason,change_ids}. finish verifies all entries and affected reviews. list/show expose safe summaries.
- [x] Add failing tests for add/full fetch/chronology/replay/pause/restore/draft-first.
- [x] Migrate schema v1→v2 with a pre-migration SQLite snapshot; retain v1 contract artifact unchanged.
- [x] Implement fixed-window pagination, thread completion, persisted inbox, bounded batches and project leases; source message identity supports trusted AppLinks.
- [x] Reuse existing business transaction with monitor scope hook and atomic step receipt.
- [x] Backup/restore and read-only browser support schema v2; restored monitors paused.

## Task 3: Read-only frontend (independent)
Files: frontend/public/data/monitoring.js, app.js, data/runtime.js, frontend/tests/monitoring.test.mjs.
Consumes API view.chat_monitors array with id,project_id,chat_name,chat_url,status,interval_minutes,history_complete,fetched_through,last_checked_at,last_completed_at,last_summary,last_error,pending_count,version,schedule (automation_id,verified_at,state). view.monitor_runs optional array. Missing arrays mean no monitors. Add project count and shared project-panel listing, existing cards/styles. Copy prompts bind data_dir/project_id/monitor_id; no POST or mutation endpoints.
- [x] Test summaries, safe links, scoped prompts and missing old-server data.
- [x] Render accessible panel with open chat, historical coverage, actual results and copy controls.

## Task 4: Skill, contract guidance and full-chain verification
Files: skills/yuplus/references/chat-monitoring.md, main SKILL routing, visualization references, docs/skills Chinese counterparts, README; tests/test_monitor_e2e.py.
- [x] Document actual CLI JSON, heartbeat creation through available host tools only, verified binding receipt, full-history chronological batching, no-change quiet runs, recovery and source boundaries.
- [x] Keep Chinese files out of installed skill paths/references; test packaging boundary.
- [x] Exercise CLI→fake Feishu executable→real SQLite/HTTP→draft/decision→review→retry→backup restore. No live group or scheduler created.
- [x] Run full Python/JS/contract/Skill validation, fresh independent review, fix material findings, record evidence and limitations.

## Progress
- Plan records user-approved execution scope; no extra approval requested for reversible implementation.

- Implemented and verified on 2026-10-21: Python 160 tests, frontend/site 40, original contracts 94; real CLI/HTTP chain with fixture Feishu provider, read-only Codex browser inspection.
- Independent review findings fixed: actual AppLink parameter, edit watermark, thread context, daily recheck scope, clock rollback.
- Two Skills validated; Chinese review copies stay outside installed trees and routing.
- Live group permissions and actual host heartbeat execution remain explicit post-binding acceptance; no real task or new release was created. Host/task identity is checked by the Skill through host tools, not cryptographically attested by the standalone CLI.
