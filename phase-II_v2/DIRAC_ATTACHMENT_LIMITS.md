# Attachment limits — source inventory for root to verify

2026-09-22. Source: `9a3fa43` / unchanged application code at `eb00071`.

**Live media setting: 20 MiB = 20,971,520 bytes.** The coordinator verified the control change and hot reload at **10:24:13.562281263 UTC**, without restarting Dirac. The source default remains 10 MiB.

These are **our code's limits**, not a claim that Discord requires them. Scope: the inspected attachment, export, media-fetch and prompt paths—not every provider, conversion timeout, frame budget or generated-media tool.

## 1. File transfer and ingestion

| Path | Enforced value | Effect / source |
| --- | --- | --- |
| Incoming non-text attachments | **20 MiB live**, default 10; hard clamp **1–25 MiB** | Skips when declared size exceeds `_max_media_bytes()`. Applies to archives too. `bot.py:10465–10469,10581–10583` |
| All incoming attachments | **50 MiB absolute ceiling** | Checked first, including text. Smaller non-text/text gates still apply afterward; this does not grant a usable 50 MiB allowance. `bot.py:10458–10474` |
| Recognized text attachments | **512 KiB** | Rejects before decoding. Independent of the media setting. `bot.py:636,10470–10474` |
| `send_file` | **25 MiB** | Independent hard-coded outgoing limit. `bot_tools.py:5086,5217–5218` |
| `shell(..., files=...)` | **10 MiB per exported file** | `_read_shell_export` raises on excess; `_send_container_file` catches it and returns `None`. Failed export can disappear from the result rather than explain the size error. `bot_tools.py:5050–5078,5823–5834` |
| `send_meme` | **25 MiB download limit** before upload | Bounded stream read. `bot_tools.py:7102,7147–7153` |
| `send_media` | **25 MiB download limit** before upload | Separate from incoming-media settings. `bot_tools.py:7178,7199–7206` |
| `send_file` / `send_media` captions | **2,000 characters** | Local validation. `bot_tools.py:5109–5110,7193–7194` |

**Outgoing acceptance has two gates:** our tool limit and Discord's actual acceptance for the uploading account/channel. The inspected send paths do not derive these caps from a verified live allowance. No oversized outbound upload was tested in this audit.

Arbitrary shell commands are a different path: the media knob does not impose a general `curl`/filesystem download ceiling. That is not native attachment acceptance or proof that a downloaded file can be understood/exported.

## 2. Counts — different stages, different limits

| Stage | Code cap | Source |
| --- | --- | --- |
| Attachment extraction | **10 selected attachments** per extraction pass, including traversed payloads | `bot.py:10446` |
| Attachment edit/media fingerprints | **8 attachments** | `bot.py:5236,5270` |
| Missing-media fallback | **5 attachment URLs** | `bot.py:12336–12347` |
| Embed extraction | Collects up to **8**, processes first **5** | `bot.py:11417,11433` |
| Sticker fingerprints | **6 stickers** | `bot.py:5244,5277` |
| Linked-media extraction | First **5 matching links** | `bot.py:11618–11635` |

These are application-stage caps. A fingerprint cap is not an upload cap. Their correspondence to Discord's limits was not live-verified.

## 3. Processing / prompt limits, not Discord transfer limits

| Stage | Limit / behavior | Source |
| --- | --- | --- |
| Text decoded into context | Keeps **50,000 content characters**, head+tail, plus a truncation notice | `bot.py:637,1861–1877` |
| SVG raster input | **10 MiB**, independently enforced | `image_media.py:11,47–49` |
| `see_image` / `see_video` | Normal live path uses the shared **20 MiB** helper | `bot_tools.py:6105–6108,6169–6176,6243–6248` |
| Image/video tool fallback | **10 MiB only if** the helper is unavailable or raises | Not an additional 10 MiB gate in the normal live path; the real bot has `_max_media_bytes()` |
| Embed / linked-media downloads | Share `_max_media_bytes()`, now **20 MiB** | `bot.py:11420,11631–11636` |
| Tool-result inline image/audio extraction | Base64 must be **strictly shorter than 5,000,000 characters** | `bot.py:13914–13938`; not a 5 MB binary-file allowance |
| Tool-result text in follow-up context | **32,000 content characters**, head+tail plus notice; base64 markers removed | `bot.py:13916,13942–13947` |

The shared media size also feeds normalization/derivative checks. Changing it therefore affects more than one attachment comparison, but **does not** change independent text, SVG, shell-export, `send_file`, caption or tool-result constants.

## 4. The `.7z` incident

Incoming order (`bot.py:10446–10484`):

1. Collect up to 10 attachment objects.
2. Check declared size against 50 MiB.
3. Check `att_size > max_size and not is_known_text`.
4. Check recognized text against 512 KiB.
5. Download, classify as media/text, and drop from this pipeline if neither.

An unknown binary is **not known text**, so it **does hit step 3**. The reported 16,220,247-byte archive exceeded the original 10 MiB setting. It passes that size comparison at 20 MiB.

This does not add archive support. This path has no `.7z` extraction/attachment-to-workspace handler. If the downloaded body is neither media nor readable text, `bot.py:10479–10484` drops it. The fallback at `12336–12350` can then wrongly suggest `see_image` for its URL. This is a separate routing/classification problem. Neither the coordinator nor the source agent downloaded, extracted or executed the archive for this audit.

**Read-path distinction:** `_read_attachment_bytes()` uses SDK `Attachment.read()` when available and returns its bytes without applying `max_bytes`. The inspected SDK reaches `get_from_cdn()` / `await resp.read()`. Only the URL fallback uses the bounded stream reader. References: `bot.py:10385–10415`, public SDK capture `message.py:348–381`, `http.py:1088–1105`. The fallback budget is `max(att_size, max_size, 1)`; a small file can therefore receive the media budget, not its own size or the text cap.

## 5. Aggregate size is not a verified 500 MB allowance

No explicit sum-of-attachment-bytes gate was found in these extraction paths. That does **not** establish a Discord aggregate allowance.

For one extraction pass with truthful declared sizes:

- 10 selected non-text files × current 20 MiB = **200 MiB**.
- 10 × maximum configurable 25 MiB = **250 MiB**.
- 10 recognized text files × 512 KiB = **5 MiB**.

These are arithmetic consequences, **not separately enforced aggregate limits, whole-turn/RSS bounds, or platform facts**. Other passes, cached context, SDK reads and base64 copies are separate considerations. Multiplying the 50 MiB absolute check by 10 while ignoring the smaller gates would produce a false accepted-budget claim.

## 6. What still needs external verification

- Discord's [File Attachments FAQ](https://support.discord.com/hc/en-us/articles/25444343291031-File-Attachments-FAQ), retrieved by the coordinator, currently states **10 MB for non-Nitro**. That does not establish this particular sender/account/channel's observed allowance. Root explicitly chose 20 MiB; it remains 20 MiB.
- Actual outgoing allowance for the Dirac account in the target group/guild: **not measured**. No Nitro status or boost-tier figures are guessed.
- Receiving an existing CDN attachment and uploading a new one are different operations. The inspected download path does not derive its limit from the bot account's upload tier; Discord-side receiving restrictions were not independently established.
- Actual Discord attachment-count and aggregate-byte rules: **not verified here**. No 500 MB total is asserted.
- **V1 parity is unknown.** No V1 private settings, archived source or other bot implementation was inspected. Root's comparison document is the next source of evidence.

## Provenance

Flash drafted the audit in `work/dirac-attachment-limits` (`38217d0`, corrected by `4ecedce`). The first draft reversed the non-text condition and produced an invalid 500 MiB estimate; it was rejected, not integrated. The coordinator re-read the operative branches, corrected the shared-helper interpretation, narrowed unsupported claims and produced this reviewed inventory. Draft history remains separate from main.

No application source changed for this report. The source agent ran no imports/tests or runtime operations. The only live mutation was root's requested 20 MiB control setting; its hot reload was independently verified.
