# Eagle MCP + Skill integration verification

Initial v0.3.32 checks (2026-11-04). That version implemented the browser handoff and the installed Skill workflow. It does not add an Eagle CLI, a server proxy, a new library registry kind, or a live MCP status endpoint. In v0.3.32 connection states belonged to the Agent conversation; website/Feishu source counts and stored preferences remain independent.

## Completed checks

- 81 frontend tests pass, including clipboard success, rejected clipboard/manual selection/retry, and duplicate-click suppression while pending. Existing catalog search, source enable/disable, Personal forms and persistence tests remain passing.
- 5 Skill contract tests pass; both installed Skills pass skill-creator validation. Eagle reference links resolve and installed Skills never route to the Chinese review copies.
- Wheel build succeeds; installed UI modules and CSS in the wheel exactly match source. The source distribution manifest includes the new Eagle reference and browser module; the existing installer copies the whole business Skill directory.
- Actual localhost gateway: the entry renders above the Official/Personal tabs; 31/31 sources remain enabled. Clicking “连接 Eagle 案例库” reports only clipboard success and the required next step, not successful connection. Reload returns to the neutral entry. No console errors/warnings observed.
- Desktop visual review and 390px viewport DOM layout: no horizontal overflow; connect button height 44px. Clipboard denial/manual fallback is covered by the unit test rather than a modified browser permission setting.
- Independent read-only Skill forward-test: no tools/config, unverified shell installer config, saved-but-unloaded config, wrong library, failed thumbnail reading, and local research without cloud-upload authorization. Outcomes retained the correct state, avoided executing unknown commands and preserved upload boundaries. No live client changes were made in this test.

## Real Eagle acceptance still required

This environment did not expose an Eagle MCP tool, and no configuration from the running official plugin was supplied. Do not label this as an end-to-end Eagle connection test.

1. Open the target Eagle library and the Eagle App official MCP Server plugin; obtain its actual client configuration. Do not invent endpoint/port/launch command from the separate Web API.
2. Exercise the Skill against the current client's supported transport. Inspect/merge only the Eagle entry, preserve unrelated settings, protect secrets and complete the actual loading/authorization step.
3. Obtain the actual tools list in the Agent session, execute a read-only query and match current library identity to the intended target.
4. Query 1–3 items and actually read a thumbnail/original with the available reader. Report metadata, thumbnail and original readability separately. Empty libraries or unavailable image/file readers remain partially verified.
5. Reconnect or switch the library, then ensure the next research verifies identity again rather than reusing a stale assumption. Do not switch the user's library as part of automated testing.
6. Conduct a bounded case search, inspect actual materials and return library identity, item ID, name and actual source/locator. No asset modification or cloud upload is part of connection testing.

## Sources and limits

- Official plugin: https://community-cn.eagle.cool/plugin/mcp-server — developer Eagle App; category switches documented.
- Official introduction: https://www.eagle.cool/blog/post/eagle-plugin-mcp-skill — MCP and Claude Code Skill are separate choices.
- Official setup guide: https://cn.eagle.cool/support/article/eagle-mcp-server — text retrieval yielded only the heading, so no concrete Eagle MCP config template is shipped.
- Codex MCP/configuration: https://developers.openai.com/codex/mcp and https://developers.openai.com/codex/config-reference ; local `codex mcp add --help` verified STDIO/Streamable HTTP and bearer environment-variable flag. The actual running client still determines effective scope and transport compatibility.

No user MCP configuration or credentials were read, changed or stored while implementing this feature.


## Connection observation update (2026-11-04)

The card now displays Agent-reported observations through `eagle status/record`, `/api/eagle`, and `eagle_connection` in `/api/view`. This is a saved result, not a live MCP probe. The installed Skill writes the exact workspace's receipt after real verification or an observed failure. No actual Eagle tools are exposed in this development session, so real MCP verification remains outside these checks.

- 280 Python tests and 85 frontend tests pass; both installed Skills pass quick validation.
- Schema 11 → 12 migration backs up first and preserves projects and source preferences. Receipts survive backup/restore; idempotent retries cannot roll back newer observations. Stale versions/observations, unsupported evidence, unknown configuration/token fields and invalid timestamps are rejected.
- Public CLI write/read and GET `/api/eagle` share the data directory; browser POST to this endpoint is rejected. Disconnection removes prior read coverage, and changing libraries replaces the identity and observation together.
- Browser checks use only `.preview/eagle-status/data` and the explicitly labeled “界面验证示例库（模拟记录）”: persisted success survives reload, then failure and reconnection update the card automatically without reloading. The count stays 31/31. No browser console warnings/errors.
- 375×812 portrait and 812×375 landscape DOM checks show no horizontal overflow; the primary button is 44px high. Poll tests cover hidden pages, sequential requests, failures/recovery and cancellation after navigation. Clipboard tests preserve the short Skill invocation with the current workspace directory and never promote copying to connection success.
- Success older than 24 hours becomes “连接待复核”; the page explicitly identifies observations as historical, not real-time availability. Existing v0.3.32 connections require one real verification and writeback before a badge can appear.
