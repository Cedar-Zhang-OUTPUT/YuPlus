# Workspace case library sources

Read this when adding, finding cases in, or removing 案例库. A library is a shared Feishu folder, independent of projects and draft/review objects. **Yu+ stores only its title, URL and registration metadata. Its contents stay on Feishu:** do not import files, bodies, excerpts, directory inventories or search indexes into Yu+ storage. Do not run folder pull/sync or background crawling.

## Register or use

- Register: use installed `lark-drive` to resolve the supplied folder's actual title, then `library add`. If inaccessible, report it and ask for an accessible link or user-supplied title; do not invent a successful read. Reuse an existing registration for the same URL.
- Whenever cases are needed: `library list` → select a relevant active registration → `library show` → use **Feishu CLI** to find/read material in that shared folder. Read the installed `lark-drive` folder-list/search guidance at this step, reusing it if already read. For keywords, prefer `lark-cli drive +search --query KEYWORDS --folder-tokens FOLDER_TOKEN --as user --format json` after checking installed guidance. Use directory listing for browsing, not as a mandatory prerequisite for search. Search within the folder and relevant subfolders; handle pagination, and verify that search results belong to this library. Use the matching Feishu Skill for each selected document's content. Yu+ is not a local case search engine.
- Present relevant cases with their actual titles, original Feishu links and reasons they fit the task. Project-specific ideas may be discussed; do not archive the case material in Yu+. Never describe a link registration or partial search as complete content collection. If a reader requires temporary files, keep them outside Yu+ data/backup storage and do not turn them into a persistent case cache.

## CLI

Use the verified workspace `--data-dir`; never `--project`. Page controls copy prompts only. After writes, verify the CLI result and refresh `#/libraries`.

```sh
yu library list --json
yu library show --library LIBRARY_ID --json
yu library add --request-id UNIQUE_ID --input request.json --json
```

Add input:
```json
{"api_version":"1","command":"library.add","name":"Actual folder title","url":"https://tenant.feishu.cn/drive/folder/TOKEN"}
```

`library update` uses the same envelope with `library_id`, current `base_version`, `name` and `url`. Receipts contain `id` (library_id), `version`, title, URL and timestamps; `meta.library_policy` reiterates remote lookup and local-only registration removal. Writes require a new request ID; retry identical requests with the same ID.

## Remove or restore

A request to delete a library means **remove its Yu+ registration only**, not delete or change the remote folder. Read `library show` first to match its ID and get the current version. Do not call Feishu deletion APIs.

```sh
yu library delete --request-id UNIQUE_ID --input request.json --json
```
```json
{"api_version":"1","command":"library.delete","library_id":"LIBRARY_ID","base_version":1}
```

Use the actual ID/version, not the example values. Removal is soft: it hides the library from the page and ordinary lists, while preserving metadata and receipts. Verify with `library list`. To recover, locate it using `library list --include-deleted`, read its current version, then use `library restore` with the matching command and the same `library_id` / `base_version` fields. Restoring only restores the link registration; no Feishu operation or content download occurs.
