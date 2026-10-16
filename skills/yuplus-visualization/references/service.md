# Open the correct service

## Discover, reuse, or start

1. Reuse the data directory and project identity established in this conversation or a copied real-mode Prompt. Resolve the directory to an absolute path. The browser URL alone does not establish the intended business project. If identity is ambiguous, inspect the existing project list and resolve it before writing.
2. Inspect a known running session, saved startup output, or existing Yu+ tab. For an occupied candidate port, inspect its listener/process (for example, `lsof -nP -iTCP:PORT -sTCP:LISTEN` on macOS). Probe its `/api/health`; do not terminate it to obtain a preferred port.
3. Reuse only a healthy service with `mode: "live"` and the intended resolved `data_dir`. Its reported `url`/`port` are authoritative. A demo, another application's listener, or a Yu+ service for another directory must not be reused for this project.
4. Otherwise start the installed CLI in a managed long-running terminal/session:

   ```sh
   yu --data-dir '/absolute/project-data' serve --port 0 --json
   ```

   Port `0` requests a free local port; a chosen free port is also valid. This is a foreground server. Read its startup JSON for the actual URL and keep its session alive. In the source checkout, `.venv/bin/yu` can be used when that is the installed environment. Check `yu --help` rather than inventing a daemon/start/stop command.
5. Verify `GET ACTUAL_URL/api/health` returns `ok: true`, `mode: "live"`, the intended `data_dir`, and actual `url`/`port`; then inspect `/api/view` or `yu --data-dir DIR project list --json` for the real project ID. `/api/view?project=PROJECT_ID` reads that project's view. Quote shell paths and use URL encoding for query values.

The CLI can initialize a new data directory. Select the intended directory deliberately: a healthy empty database at an accidental path is not the user's missing project. For installation/runtime issues, consult the business skill's setup reference rather than switching to a sample service.

Record the launched session/PID, resolved data directory, and actual URL together. Stop a server you started through its own terminal/session when stopping it is needed. Before using a stored PID, recheck the current process identity, listener and health binding; PIDs can be reused. Do not kill all Python/Node processes or unrelated services. A service restart may change a dynamically allocated port.

## Routes and opening

Append these routes to the verified base URL; replace IDs with returned identities:

| Destination | Hash route |
| --- | --- |
| Project list | `/#/` |
| Object definitions | `/#/types` |
| Information collection | `/#/p/PROJECT_ID/draft` |
| Specific draft object | `/#/p/PROJECT_ID/draft/OBJECT_ID` |
| Review | `/#/p/PROJECT_ID/review` |
| Specific review or shared Q&A | `/#/p/PROJECT_ID/review/OBJECT_ID` |
| Saved original materials | `/#/p/PROJECT_ID/sources` |
| Changes and decisions | `/#/p/PROJECT_ID/history` |

Use an available Codex/browser opening tool with the full URL. Do not close or repurpose unrelated user tabs. Hash routing changes the reading location, not business state. A copied link does not encode the selected historical version: verify the version shown in the page and preserve its revision in any edit reference.

The UI initially shows “正在读取项目内容”. A successful empty project/list and “无法读取项目内容” are different states. The latter has “重新读取”; it does not mean the project has no data. CLI writes become visible after the sidebar footer's “刷新页面” or a browser reload. Navigation inside a loaded project can reuse its existing view, so navigating alone is not a guaranteed refresh.

## Demo is separate

`npm --prefix frontend run dev` starts the explicit frontend demo (default port 7801; `-- --port PORT` selects another). Its health mode is `demo`; it does not read the user's database. Demo source links and cached text files are examples. Never use sample IDs, revision pointers, local demo links, or a demo update Prompt as production write inputs. Do not start a demo as a fallback when a real service fails.
