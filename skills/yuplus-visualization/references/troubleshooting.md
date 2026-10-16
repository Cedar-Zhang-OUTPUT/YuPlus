# Resolve the observed failure

| Observation | Check and next action |
| --- | --- |
| Address will not load | Inspect the known session/listener; verify `/api/health` at its actual port. Start the intended live service if absent. Do not kill another process to take 7801. |
| Demo projects appear | Health is `demo` or the wrong tab is open. Locate/start the live service bound to the intended data directory and open its returned URL. Never import sample content to repair an empty real project. |
| Healthy service, wrong or no projects | Compare health `data_dir` with the established project directory, then list project identities. Same names can occur. A fresh accidental directory is not evidence of data loss. |
| “无法读取项目内容” | Read the error and health/API status; verify directory, access and installed version. Use “重新读取” after correction. A read failure is not an empty project, and should not fall back to cached other-project data. |
| “项目不存在” or missing object | Verify the ID and project ownership in that service. Use real returned IDs, not screenshot/demo IDs. Do not create a duplicate to make a stale URL work. |
| Saved CLI change is absent | Check successful receipt and data directory; refresh using “刷新页面”. Check whether a historical object version is selected, then return to current. Route navigation alone may reuse loaded data. |
| Version menu or media does not work | Check browser support: the version menu uses native popovers; media uses browser format/codec support. Use a compatible browser or read the exact saved revision/asset through supported tools. Do not claim all browsers render every file. |
| “无法复制” | Clipboard access failed. Retry through the visible button and check browser permissions/context. If necessary construct the equivalent identity-bound request from verified data or help the user copy readable text; never report the copy as successful. |
| No original link or title | The source may be local or only an address/title-not-yet-read may have been saved. Use its snapshot and stored identity; do not invent a remote title or URL. |
| File absent or content changed | Inspect registered asset availability and selected snapshot. An external file may have moved, disappeared or changed hash. Preserve historical provenance; use the business import/append workflow for a new file version rather than passing it off as the old asset. |
| Finder button absent/fails | It requires macOS, service support and an available registered asset. On other platforms use the available browser file link/save flow. Recheck availability after moving files; no arbitrary-path reveal workaround. |
| Missing basis / cannot compare | Reread the exact cited revisions and evidence. Keep unknown distinct from unchanged/deleted; do not manufacture replacement relationships or a synchronized state. |
| Export did not create a document | The browser only copies a Prompt; local bundle preparation only writes files. Actual execution needs the export request, Feishu CLI/authentication, document creation/write and readback. Preserve prepared files and report concrete authorization/login/permission failures. |

Use available browser inspection to verify the failing control when useful. Report what was actually observed versus inferred from source. A screenshot from a design handoff is not proof that today's live service, assets, clipboard, or Feishu export worked.
