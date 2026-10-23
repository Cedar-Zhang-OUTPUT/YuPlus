# Setup and material access

Read this for first setup, a changed environment, or the relevant material source. Do not run all checks for every task.

## First setup

1. If this Skill contains `installation.json`, read its CLI and chosen data directory once; use [operations.md](operations.md) for the unified installer and service. Locate the installed `yu` executable or the repository's `./yu` / `.venv/bin/yu`. Inspect `yu --help` if unfamiliar. Use the same executable and explicit data directory throughout the task. `yu --data-dir DATA_DIR doctor --json` checks the local SQLite runtime; it does not check Feishu and may initialize a new data directory.
2. If Yu+ is missing, use the repository's maintained installation instructions. Do not silently create an alternative datastore or edit the application to bypass a runtime error. The current development install needs Python >=3.12 with SQLite >=3.51.3. Skill installation alone does not install the application.
3. At this initial environment check, look for `lark-cli` and inspect its help/version. When available, use the installed `lark-shared` authentication guidance; the version checked for this skill supports `lark-cli auth status --json --verify`. This read-only verification needs network access. Keep credentials out of output. A verified login does not prove access to every document.
4. If Feishu CLI is missing, login is unavailable or network verification fails, report the specific limitation. Continue local/oral work. For a Feishu-only task, offer authentication repair or a user-provided export, not a demand for all project fields. Recheck authentication after a relevant error or environment change, not before every normal fetch.
5. Inspect `project list` only if project identity is unknown. Ask for the project only when ambiguity matters. A project name, prototype selection, folder name or default `working_scene` is not a reliable substitute for the actual project ID.

## Feishu documents and exports

- Prefer the installed `lark-doc` skill for document/wiki reading; `lark-drive` for file download/export or uploaded exports. Use the specific skill's reference and actual command help. If those skills are absent, use the installed Feishu CLI's supported help; do not invent its flags. The locally checked document reader is `lark-cli docs +fetch --doc URL` (whole document when scope is omitted); partial reads must retain their scope.
- Use the appropriate user/bot identity. Follow installed authentication guidance for actual errors. Do not initiate broad new authorization or external writes simply to collect one material.
- Obtain the real title, concrete resource token/type and, if returned, actual revision. Resolve wiki/share links to the underlying resource before passing them to Yu+. For docx, the Yu+ provider key ends with the actual document token; preserve a stable prefix when one is already used. Supported URLs/types are validated by the installed application. Do not invent a revision: use null when unknown. In particular `--revision-id -1` means “latest requested”, not a captured revision of -1.
- Import fetched content or an actual downloaded export. Merely registering a link is not proof of reading its body. Use the title as the Markdown link label. The browser may open a title link in a new tab; use available host capabilities when explicitly asked to open it.
- For downloaded assets, follow that installed Feishu CLI's path rules, then provide the actual resulting local path to Yu+. Different tools may accept different path forms.
- When the user reports a source update, compare the newly fetched content with the stored snapshot as needed; append the source, update affected draft items, then regenerate affected review content. Do not overwrite old evidence or assume every object is affected. If there is no substantive change, report the no-op.
- Each new service start checks saved Feishu sources in the background; `source check` runs an on-demand scan. Read [operations.md](operations.md) for comparison markers and handling observed updates. Checks save observations/errors only, without importing content or changing draft/review. Refresh the page to see results; no recurring scheduler or push notifications are provided.
- Sending a result to Feishu is an external action, separate from local import. Use the user's actual instruction and destination. Yu+ has no export-recording command yet; do not pretend an externally created link has been recorded as a versioned export.

## Materials shared in a group

For group-origin documents, files, images or meeting minutes, read [chat-materials.md](chat-materials.md) before deciding what to save. Save readable local content with copied assets, preserve the verified message locator as provenance, and keep the material separate from the contextual discussion segment. Receiving a file tag is not reading the file.

## Local files, images and video

Use an available PDF/document/media skill or direct tool reading when appropriate. Preserve original bytes with `assets[].storage="copy"` unless the user intentionally prefers an external reference (such as a very large video). External references can become unavailable or change.

Record only observed content. A file can be stored without claiming to have parsed every page, watched every frame or heard all audio. Use actual page/block/time locators where available. Describe an unexamined attachment honestly in conversation; do not invent backend “reading / partially read / processed” statuses.

A partial textual extraction is `capture_scope.kind="selection"`, with its actual locator, and `advance_head=false`; it can still carry the original file as an asset. Only assert `whole_resource` for the resource actually captured at that scope. Separate supplied file content from the Agent's interpretation.

For screenshots and dated files, use visible dates, surrounding messages and available source metadata to establish context before asking for it. Do not replace a document's business dates with the import date or assume old dates mean overdue work. Follow the user's historical/replay scope when given. Distinguish an explicit requirement, a tentative value and a creative option; a TBC or an unprovided technical detail is not automatically a client question. Route remaining uncertainty by purpose (D15 concrete client clarification exchanges; D24 open project exploration), using [objects.md](objects.md#d15-客户-qa-问题表qa).

## Spoken input and review instructions

Use `provider="oral"`, typically `resource_type="statement"`, and preserve the actual words available in the conversation. Attribute the speaker accurately in provenance. Label summaries/transcriptions as such; do not invent verbatim quotations, meeting times, decision authority or an audio recording.

An instruction to change a project's adopted position is decision evidence. An instruction only to rewrite a review block becomes evidence for a draft expression guide. Do not create a new source for an already-recorded instruction just to manufacture a fresh review cause.

## Export saved Review

For a requested Feishu export, read [export.md](export.md). It covers whole-project scope, local preparation, remote writing/readback, receipt recording and recovery. Reuse once read.
