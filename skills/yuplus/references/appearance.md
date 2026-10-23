# Workspace avatar

For changing the top-left logo/avatar, use the current Yu+ data directory, without `--project`. No project, source, draft or review reads/writes are needed.

1. Use the image the user attached. If absent, ask them to attach it; copying the prompt does not upload an image.
2. Preserve the original. Resize a temporary copy proportionally to at most **256 px** on its longest side. Export a static, non-interlaced, 8-bit **PNG**, preserving transparency where present. Do not generate a replacement design or crop without instruction. On macOS, `sips -s format png -Z 256 ORIGINAL --out TEMP.png` provides a lightweight conversion. Quote paths; use a fresh temporary destination. Else use an available image conversion tool. The CLI accepts up to 512×512 and 256 KiB; shrink further if necessary.
3. Read `yu logo show --data-dir DATA --json` for `data.version` (initially 0). Apply with a fresh request ID:

```sh
yu logo set --data-dir DATA --request-id req_logo_unique --input /tmp/logo-request.json --json
```

```json
{"api_version":"1","command":"logo.set","base_version":0,"local_path":"/absolute/path/to/compressed.png"}
```

Use the actual version and temporary file path. Yu+ validates the image, strips nonessential PNG metadata, compresses it and stores it inside SQLite. Its backup/restore includes the avatar. The original and temporary image can be removed independently after successful verification; never remove the user's original.

4. Verify `logo show`, refresh the existing local browser view and inspect the avatar. A restart is unnecessary. State completion only after the CLI succeeds. On a version conflict, reread the logo version before retrying; reuse a request ID only for the exact same attempted write.

If explicitly asked to restore the default logo, use `logo reset` with the same flags and `{"api_version":"1","command":"logo.reset","base_version":CURRENT}`. Reset preserves the incrementing version. It does not delete projects or source files.
