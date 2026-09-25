# Server prompts

The remediation contract below is not a claim that the running temporary bot has been replaced. Use your configured prefix; examples use the repository convention `!`.

- **`!prompt TEXT`:** replace the server prompt and receive a short acknowledgement, not an echo of its body.
- **`!prompt` alone:** show a small prompt inline; above 1,800 UTF-8 bytes, return `prompt.txt` instead of flooding the channel with chunks.
- **`!longprompt` alone:** download the current server prompt as UTF-8 `prompt.txt`.
- **`!longprompt` with one attached `.txt` file:** replace the server prompt with the uploaded text; do not add inline arguments.
- **`!clearprompt`:** clear the prompt; an empty upload does not clear it.

These commands share bot-admin authorization, disabled-command controls and prompt storage. Guilds retain their own server-ID keys; DMs retain the existing `DM` key. This is not another prompt layer or a change to the base personality.

## Bounds and preservation

- New inline and uploaded server prompts have a dedicated **16 KiB UTF-8 ceiling**. Oversize input is rejected before persistence, never truncated.
- Existing stored prompts remain exportable up to the separate **512 KiB text-file ceiling**. An oversized legacy prompt is omitted whole from model context with an actionable diagnostic until replaced; its stored text is not deleted or silently rewritten. Core identity and tool instructions are not middle-trimmed to accommodate it.
- Exactly one attachment with a case-insensitive `.txt` suffix is accepted. Invalid UTF-8, zero-byte files, inline upload arguments, multiple files and oversize files are rejected without changing storage.
- Uploaded text is neither normalized nor clipped: snowflake syntax, newlines, whitespace, backticks, Unicode and an existing UTF-8 BOM survive. Whitespace-only text is not silently converted into a clear operation.
- Replies disable mentions. Uploaded prompt bodies are not echoed, and downloaded files contain actual text rather than rendered Discord mentions. No model processes the upload.
- Attachment metadata is checked before downloading and actual bytes afterward. The Discord SDK buffers the download; this is not a streaming transfer-memory bound against false metadata.
- A stored prompt above the export ceiling is refused explicitly, never partially exported. If persistence succeeds but acknowledgement fails, the save is not rolled back; download the prompt to verify it.

General media limits are unchanged. Source review, isolated QA, artifact validation and actual Discord acceptance are separate receipts in the current status/audit records.
