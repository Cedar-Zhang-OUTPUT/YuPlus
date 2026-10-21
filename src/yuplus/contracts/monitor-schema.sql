CREATE TABLE chat_monitors (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), chat_id TEXT NOT NULL,
 identity TEXT NOT NULL, chat_name TEXT NOT NULL, chat_url TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('enabled','paused','removed')),
 interval_minutes INTEGER NOT NULL CHECK(interval_minutes>0), version INTEGER NOT NULL DEFAULT 1,
 history_complete INTEGER NOT NULL DEFAULT 0, fetched_through TEXT,
 next_due_at TEXT NOT NULL, last_checked_at TEXT, last_completed_at TEXT,
 last_summary TEXT, last_error TEXT, schedule_json TEXT NOT NULL DEFAULT '{}',
 threads_json TEXT NOT NULL DEFAULT '[]', last_recheck_at TEXT,
 created_at TEXT NOT NULL, UNIQUE(project_id,identity,chat_id)
) STRICT;
CREATE TABLE monitor_runs (
 id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL REFERENCES chat_monitors(id), project_id TEXT NOT NULL REFERENCES projects(id),
 status TEXT NOT NULL CHECK(status IN ('fetching','processing','complete')),
 window_start TEXT, window_end TEXT NOT NULL, cursor_json TEXT NOT NULL,
 fetch_complete INTEGER NOT NULL DEFAULT 0, initial INTEGER NOT NULL,
 created_at TEXT NOT NULL, completed_at TEXT, summary TEXT
) STRICT;
CREATE TABLE monitor_leases (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), run_id TEXT NOT NULL REFERENCES monitor_runs(id),
 token TEXT NOT NULL, expires_at TEXT NOT NULL
) STRICT;
CREATE TABLE monitor_messages (
 id TEXT PRIMARY KEY, monitor_id TEXT NOT NULL REFERENCES chat_monitors(id),
 message_id TEXT NOT NULL, version INTEGER NOT NULL, fingerprint TEXT NOT NULL,
 created_at TEXT NOT NULL, observed_at TEXT NOT NULL, remote_updated_at TEXT,
 payload_json TEXT NOT NULL, source_version_id TEXT,
 disposition TEXT CHECK(disposition IN ('applied','no_change','clarification')), reason TEXT,
 resolved_run_id TEXT REFERENCES monitor_runs(id), UNIQUE(monitor_id,message_id,version)
) STRICT;
CREATE INDEX monitor_pending ON monitor_messages(monitor_id,disposition,created_at);
CREATE TABLE monitor_steps (
 run_id TEXT NOT NULL REFERENCES monitor_runs(id), step_key TEXT NOT NULL,
 command TEXT NOT NULL, request_json TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
 message_versions_json TEXT NOT NULL, result_json TEXT, created_at TEXT NOT NULL,
 PRIMARY KEY(run_id,step_key)
) STRICT;
PRAGMA user_version = 2;
