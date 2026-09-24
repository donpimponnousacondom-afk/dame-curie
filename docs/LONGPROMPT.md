# Attachment-based server prompts

`longprompt` is a separate command. The existing `prompt` command, including its message-length limitation, is intentionally unchanged.

Use your configured prefix: `?` for temporary Dirac, repository default `!`.

- **`?longprompt` alone:** download the current server prompt as UTF-8 `prompt.txt`.
- **`?longprompt` with one attached `.txt` file:** replace that server's prompt with the file's UTF-8 text. Do not add inline prompt text to the command.
- **`?clearprompt`:** the existing command clears the prompt; an empty upload does not.

The command uses the same bot-admin authorization, disabled-command control and prompt storage as `prompt`. Guilds retain their own server-ID keys; DMs retain the existing `DM` key. This is not another prompt layer or a change to the base personality.

## File contract

- Import and export use the existing **512 KiB text-attachment ceiling**, measured in UTF-8 bytes, not rendered Discord characters. General media limits are unchanged.
- Exactly one attachment, with a case-insensitive `.txt` suffix, is accepted for upload. Invalid UTF-8, zero-byte files, inline arguments, multiple files and oversize files are rejected without changing the stored prompt.
- Text is neither truncated nor normalized: snowflake syntax, newlines, whitespace, backticks, Unicode and an existing UTF-8 BOM survive. Whitespace-only text is not silently converted into a clear operation.
- Replies are short, disable mentions and do not echo the prompt body. The downloaded attachment contains the actual text, not a screenshot or Discord-rendered mentions. No model processes the upload.
- Upload metadata is checked before downloading, and actual bytes afterward. The Discord SDK buffers the download; this is not a streaming transfer-memory bound against false metadata.
- A stored prompt above the export ceiling is refused explicitly, never partially exported. Upload, storage and send failures use the existing command-error path. If a save succeeds but the acknowledgement fails, the save is not rolled back; download the prompt to verify it.

Implementation and isolated tests are source acceptance only. Building, deploying and observing a real Discord attachment roundtrip require their own acceptance; this document does not imply the running bot already has the command.
