# Installation, recovery and source checks

Read only the section needed now. These commands supplement cli.md; they do not create another business scenario or an approval gate.

## Installed location and service

If this Skill contains `installation.json`, read its `cli`, `python` and `data_dir` on first use; these are installed paths, not example paths. Reuse them unless the user chooses another existing workspace. A copied real-project reference may select a different data directory; verify it deliberately. Do not assume the development `.preview` directory is production.

From a trusted local checkout, `./install.sh` installs the application and both Skills, reuses a suitable Python or prepares a private runtime through the official uv installer, checks Python >=3.12 / SQLite >=3.51.3, initializes the selected data directory, and checks Feishu authentication. `--prefix`, `--skills-dir` and `--data-dir` select explicit destinations. `--python PATH` selects an existing interpreter; `--managed-python` exercises the private-runtime path. No shell profile is edited. It refuses to overwrite unmanaged or modified Skills; it does not install or log into Feishu for the user. Read lark-shared for missing authentication. The initial release targets macOS.

`yu --data-dir DIR start --json` starts or reuses the managed local service. `status` reports a verified address; `stop` stops only a service whose directory, PID and instance ID all match. `serve --port 0` remains a foreground option. Open the returned URL using an available Codex browser tool. On each new service start a background source scan runs; service reuse does not promise a new scan. Refresh the existing page after a background scan or CLI write to see saved results.

## Complete backup and recovery

- `yu --data-dir DIR backup create --output NEW_BACKUP_DIR --json`
- `yu backup verify --input BACKUP_DIR --json`
- `yu --data-dir NEW_DATA_DIR backup restore --input BACKUP_DIR --json`

Backup contains a consistent SQLite snapshot and all registered original bytes, including external references. If any registered bytes are missing/changed, backup fails rather than declaring a partial copy complete. Restore requires a nonexistent destination. It verifies hashes, database integrity and reference coverage, preserving immutable IDs/history; external files are remapped to restored copies without rewriting source records. Start the restored directory, inspect the expected projects and key materials before switching work to it. Do not copy only an active SQLite main file, remove the original data directory, or treat export Markdown as a backup.

## Remote source updates

`yu --data-dir DIR source check --project PID --json` scans a project; add `--source SID` to check one source. Omitting project scans all saved Feishu sources. `source list` exposes the last observation, error and check time. Startup checks and manual checks do not import content, change draft/review, or fabricate business change history.

Docx uses the returned revision. Other supported resources use `mtime:<latest_modify_time>` from metadata; when collecting those resources save the actual observed marker in `snapshot.provenance.remote_marker`. A marker obtained before/after a content read is not proof of a coherent snapshot if it changed during that read. Never invent a marker. Missing comparable capture evidence stays `unknown`; a successful metadata call is not proof of unchanged content. Pending changed observations survive later errors until a new capture invalidates them. Check failures do not block local work.

When the user asks to synchronize, or a source update falls within already-authorized project maintenance: fetch the changed material using its matching Skill, append a real full snapshot, update affected draft items with sources, then update dependent review. Do not blindly regenerate all objects or infer a user's new adopted decision from ambiguous source conflicts. Review-only wording feedback still follows draft expression_guide first.
