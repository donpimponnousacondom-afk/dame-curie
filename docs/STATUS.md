# dame-curie status

The first section was written on 1 November 2026. The sections after it
are older. Their headings give their dates where they have one.

## Behaviour changes, 31 October to 1 November 2026

Each row is one merge to `main`, in merge order, except row #4. It also holds
PR #6, which merged into the #4 branch 33 seconds before #4 merged to
`main`. Use this list when a behaviour changes in the next days.

These facts come from the session record, not from the repository:
- Root made the coordinator director of dame-curie on 31 October 2026.
- The coordinator deployed each merge to throne-v2.
- Sonnet and Haiku reviewed each PR. The repository holds review
  digests as PR comments for #4 to #12, and as commit or PR text for
  #13, #15 to #18, #20, #22 and #23.

How to revert one change:
1. Create a branch from `main` and run `git revert <commit>`.
2. Revert newer rows first. Later PRs touch the same files, so an old
   revert can conflict. #17, #18 and #20 are three steps of one series.
3. Open a PR, review it, merge it, then deploy.
4. Extra steps:
   - #4 and #13 changed `scripts/publisher/*.py`. Reinstall them to
     `/opt/dame-curie/scripts/publisher/` and restart
     `dame-curie-publisher.service`.
   - #4, #7, #27 and #28 changed `compose.yaml`. Install the reverted file as the
     deployed copy.
   - The deployed copy is `/opt/dame-curie/compose.yaml`, next to the
     deployed `scripts/instance.py`. Source: the coordinator's deploy
     script (session record).
   - #7 renamed `DAME_CURIE_PUBLIC_BASE_URL` to
     `DAME_CURIE_IMAGE_PUBLIC_BASE_URL` in `docker/bot.env.example`. The
     operator's `bot.env` got the same rename at deploy (session record).
     A revert of #7
     needs the old name back in `bot.env`.

| PR | Commit | Change | Watch for |
| --- | --- | --- | --- |
| #4, #6 | `afc9383` | The throne-v2 commits that ran live since 9 October 2026 (119 files). The tool argument `reasoning` is renamed to `explanation`. The reasoning and `<think>` filters are removed. The prompt invites batched independent calls, with a cap of 10 calls per response and byte limits. One AI slot is kept free for human replies. `compose.yaml` pins OpenBLAS and OpenMP to one thread. RAG search scores in one matrix pass. The commit hook, the GitHub workflow and the image build refuse em and en dashes. The publisher repair is recorded. #6 merged into the #4 branch as `3f87faa`, which is not on `main`; its change is inside `afc9383`: an over-limit batch returns a refusal with the exact cause, and jobs report an unresolved tool error. A revert of `afc9383` reverts #4 and #6 together. | "Error - " tool results in long tool rounds; "AI slot wait" log lines. |
| #7 | `57083ed` | The tool history has its own prompt allowance: 42 messages and 96,000 characters, and a note marks dropped rounds. `DAME_CURIE_PUBLIC_BASE_URL` is renamed to `DAME_CURIE_IMAGE_PUBLIC_BASE_URL`; the old name stops startup with its cause. `see_image` and `image_generator` read her own images from disk. Reasoning-shaped JSON stays visible. The bot class is renamed to `DameCurieBot`. `instance.py` refuses to start without the smoke directories, and `compose.yaml` mounts them. The voice wake word default is `curie`. | Forgetting earlier tool results; wrong image links; startup refusal after a config change. |
| #8 | `8d72c97` | Background jobs compact their history with a model summary at about 180,000 tokens. | "compacted" notes in job threads; jobs that fail with a compaction cause. |
| #9 | `338534a` | Tool images stay attached for the whole turn. A turn that stops posts "Stopped: <cause>.". An empty final answer posts "No reply: my final response was empty.". | These notices in channels. |
| #11 | `2972a05` | Attachment URLs stay in history. | Later turns that fetch an old attachment. |
| #10 | `12aa2c6` | Text written beside tool calls is posted as a progress update. Job summaries are assistant messages. `see_image` reads any local image file and refuses other files. | Extra short messages during tool work. |
| #12 | `c5694fc` | The PR changes tests only. | No runtime change. |
| #13 | `ed5cb2f` | Publisher: top-level hidden folders of a site (for example `.data`) and their files stay on the remote. A local file in such a folder is uploaded. Deleting the whole site locally deletes them too. The prompt states the sync rules. | Data in `.data` folders after a sync. |
| #14 | `51bb813` | The log names a missing embedding setting. | "Embedding failed (...)" log lines. |
| #15 | `6e6e3a0` | Her own history lines no longer carry reply, mention or autonomy notes. User lines say "replying to". The chat rules say history metadata never goes in a reply. | "reply_to=" or notes copied into replies. |
| #16 | `618a2f6` | History notes use braces: `{replying to="Name(id)", quote="..."}`. Her own lines get the reply note back. | A copied `{replying to=...}` in a reply. |
| #17 | `d1a80c2` | No cosmetic rewrite of replies: brackets, repetition, `\n`, sent markers, `Name(id)` pings and `<url>` stay as written. `scrub_repetitions` is retired. | Repeated words, `__MESSAGE_SENT__` or `[Dame Curie]` in replies. |
| #18 | `b686228` | No tool-markup stripping: XML, pipe, DSML and `<arg>` tool markup, tool JSON and injected context tags reach Discord as written. The JSON catch-all and the empty-fence remover are removed. | Raw tool markup or `<system-reminder>` text in replies. |
| #21 | `d181ccd` | The self-repetition note skips the stored time prefix and counts only her own rows. | The note "You have opened N of your last M messages with ...". |
| #20 | `9f71490` | Tool calls written as text are not executed. A failure to read tool calls fails a background job with its cause. | Tool-call text posted in a channel instead of an action. |
| #22 | `d648323` | A malformed native tool call names the call and the exact cause. Arguments with two wrappers and one JSON string were refused; they are accepted now. | "Malformed native tool-call batch: call ..." in the log. |
| #23 | `153caa9` | The provider log line states `input=`, `input_source=` and `cached=` tokens. First live log measurement, 1 November 2026 (not in the repository): 9,232 of 17,470 input tokens cached. | Read `cached=` to measure prompt-cache hits. |
| #24 | `9bbf2dd` | The bot no longer runs the startup REM backfill. It re-inserted up to 500 old replies on each start with the current time, so they moved to the newest end of her history. | History in time order after a restart. |
| #26 | `170d5b5` | No intent is read from the words of a reply. The `_PROMISE_RE` regex took "checking" in a finished reply for an "on it" promise, called the model again, and the reply posted twice (14:09 CET, 1 November 2026). `send_message` now ends the turn whatever its words. Text written beside working tool calls posts as a progress update before those calls run. Media, final and pausing calls keep the after-call rule. | An update that posts after the tools, or a reply that posts twice. A message "Stopped: the progress update could not be posted (...)". |
| #27 | `0b9c661` | Prompt query embeddings have their own lane, so they no longer wait behind the bot's queue of background writes (web pages, tool records). Before, a query waited 24.8 s on 1 November 2026 (live log, not in the repository). A query embedding that takes 1 s or more logs "Query embedding took ...", also when it times out or fails. #27 also set `OLLAMA_NUM_PARALLEL` to "2"; #28 sets it back to "1" because it has no effect (see #28). | "Query embedding took" lines and the `entity_profile` time in "Prompt build" lines. |
| #28 | `git log --grep '(#28)'` (the squash commit does not exist before the merge) | `OLLAMA_NUM_PARALLEL` is "1" again. With the value "2", Ollama 0.33.3 loaded `qwen3-embedding:0.6b` with one slot (`n_slots = 1`). Live measurements on 1 November 2026, after #27 (not in the repository): a 200-character query alone took 0.24 s. The same query during a 6,000-character background piece took 7.70 s. That piece alone took 7.54 s. In a second run, a query that arrived during the first of two background pieces finished before the second piece. | A total time above 8 s in "Query embedding took" lines. The "query lane wait" field does not include the time in the Ollama queue. |
| #29 | `git log --grep '(#29)'` (the squash commit does not exist before the merge) | No compose delay before a send. `_reply_typing` slept 0.35 s to 1.2 s (0.3 s plus 1 s per 120 characters) before the final reply and before `send_message` sends, when the typing indicator showed. For 66 characters the formula gave 0.85 s. Measured on 1 November 2026 (live log, not in the repository): that 66-character `send_message` took 1.24 s from start to delivery. Not measured: the share of the Discord typing request in the rest. The typing indicator stays. | Replies that arrive faster after the model call. |
| #30 | `git log --grep '(#30)'` (the squash commit does not exist before the merge) | Warm memory recall. Cold: there is no query vector of this person in this channel from the last `recall_warm_seconds` (900 s). The turn then waits for the vector of its message, as before. Each turn that gets a vector stores it, so a conversation with gaps under 900 s stays warm while its vectors arrive. Warm: the memory searches run at once with the previous vector, and the turn does not wait for the embedder. A background task computes the vector of the new message for the next message. Cached: a message whose vector is in the cache uses it. `recall_warm_seconds` 0 turns warm recall off. A warm prompt says that its memory recall is ranked for an earlier message, and since #32 it states the age of that vector. Measured before #30 on 1 November 2026 (live log, not in the repository): a 424-character message waited 1.46 s for its query vector. Its query lane was idle, but Ollama ran the background embedding of the same message first. Not measured: the time a warm turn saves. | "Memory recall: cold ...", "warm ..." and "cached" lines. Warnings "Memory recall: ... no query vector ..." with their cause. Recall that misses a new topic for one message. |
| #31 | `git log --grep '(#31)'` (the squash commit does not exist before the merge) | `bot_output` rows (her replies and tool records) are stored but not embedded. No memory search reads that kind: the prompt searches read `entity`, `ltm`, `message` and `web_result`, and `rag_relevant_context`, the only reader of `bot_output`, has no caller. The maintenance backfill skips the rows, and the status counts them as excluded. Measured before #31 on 1 November 2026 (live log, not in the repository): each probe turn sent 6 embedding requests. 3 of them came after her reply. Which rows they were is not measured. Rows embedded before #31 keep their vectors; no search reads them. Their count is not measured. | Fewer embedding requests per turn in the Ollama log. "Query embedding took" lines. |
| #32 | `git log --grep '(#32)'` (the squash commit does not exist before the merge) | Root's default (1 November 2026): she sees harness failures with their cause. A failure while her prompt is built adds a line under "Harness failures while this prompt was built (tell root if they matter for your answer)". Failures that add a line: no query vector on a cold turn; a failed background vector of the previous message; the person's facts; the relevance search of those facts; the long-term memory and older-message sections; cached web results; cross-context facts; the knowledge graph block; the inbox notices; the names in the conversation. Inside `rag_search`, a row with unreadable metadata, an unreadable row and a failed filter for downvoted memories add a line through `SEARCH_ERRORS`. Each failure also logs a warning. Before #32, eight of these logged only at debug level, and the inbox failure and the timestamp failure did not log at all. A cached query vector is now served during the query pause. A warm prompt states the age of the vector it uses. A recalled row whose timestamp cannot be read keeps no age label and adds a line too. | "Harness failures" lines in her prompt, and her reports of them in chat. |
| #33 | `git log --grep '(#33)'` (the squash commit does not exist before the merge) | The line about the current message shows the time in the container time zone with its name, for example "Sun 2026-11-01 17:33 CET". The legacy code used a fixed UTC-4 offset labelled "AST". Root (1 November 2026): the bot uses the container time zone and never a hardcoded one. Root named the current container zone: Europe/Madrid. A test refuses fixed zones in every `.py` file outside `tests/` and `audit/`. History lines do not change. | The time on the "User:" line of her prompt. |
| #34 | `git log --grep '(#34)'` (the squash commit does not exist before the merge) | One row per Discord message. The gateway stores each message of hers under its Discord id (with the time prefix) and writes first. Since #34 it stores her message before every gate of `on_message` (commands, stop, disabled bot, blocked, not-allowed and solo channels). The bot no longer writes copies (`bot_reply`, `bot_send_message`, `bot_update`). A reply that is not fully delivered stores only a note row (`bot_delivery_note:<id>`). Measured before #34 on 1 November 2026 (live database metadata, not in the repository): her rows were 321 gateway rows and 174 copies (61 `bot_reply`, 47 `bot_send_message`, 7 `bot_update`, 59 `rem_backfill`); no stored row held a delivery footer; in the test channel the gateway row came 0.1 s to 0.3 s before the copy. `rag_maintenance.py dedupe-self-copies` counts the old copies, and with `--apply` it deletes a copy in two cases, after an owner-only backup of the database. First: it is `bot_reply:<id>` or `bot_update:<id>`, and the gateway row `<id>` of the same author exists. Second: a gateway row of the same author in the same channel holds exactly its text. `bot_send_message:<id>` holds the id of the message she answered, so it matches by text only. | Each message of hers once in her history. |
| #35 | `git log --grep '(#35)'` (the squash commit does not exist before the merge) | Background jobs mask old tool results. Masking runs in batches. It waits until at least 8 rounds lie between the oldest round with an unmasked result of 400 characters or more and the newest round, counting both. Then every such result older than the newest 4 rounds becomes one line. The prompt prefix therefore changes once every 4 steps. The line keeps the first line of the result, so an error stays visible: "[masked] the <tool> result of an older step (N characters) is masked to keep the job prompt small. It began: <first line> Call it again only if repeating it is safe." A masked result never changes again. The model summary at the compaction limit (#8) stays as the last stage; it now reads the masked lines of older rounds. A history with a broken call/result pairing or a malformed call stops the job with "tool-result masking failed at step N: <cause>". Root approved masking for background jobs only (1 November 2026). Source: Fable's research and JetBrains Research, arXiv 2508.21433. Not measured: the cost effect with provider caching. | "background job ... masked N older tool result(s)" log lines; fewer "Context compacted" posts; `input=` and `cached=` per job step. |
| #36 | `git log --grep '(#36)'` (the squash commit does not exist before the merge) | The masked line of a job names the call that produced the result: the tool and its arguments without `explanation`, cut at 120 characters. Example: "[masked] the result of the older call shell {"command":"cat index.html"} (3,021 characters) is masked to keep the job prompt small. It began: <first line> Call it again only if repeating it is safe." Dame Curie asked for it after the live test of #35 (1 November 2026): "a bare first line is ambiguous when output starts with a header". The marker is longer now, so a result of about 400 to 550 characters often stays unmasked (a result stays when its marker is not shorter). That is accepted; the saving in that size range is not measured. A result that stays for that reason does not count as open, so it never holds the batch trigger of #35 and masking keeps running once every 4 steps. Measured in that test (job f37ba26c, 21 steps, live log, not in the repository): masking ran 3 times and removed 11,650, 8,938 and 18,246 characters; the input fell from 21,539 to 15,906 tokens at step 21 (the new results of that step also added tokens; their share of the difference is not measured); the step after each masking had its newest rounds uncached. | Masked lines that name their call. |
| #37 | `git log --grep '(#37)'` (the squash commit does not exist before the merge) | Provider retries wait 5 s, then 20 s, then 60 s for each later retry (before: 10 s more for each retry). The default attempt count is 3 (before: 5); `OPENAI_RETRY_ATTEMPTS` still sets it. The context watcher has one total limit for the slot wait and all provider attempts. The provider gets the time that is left as its attempt timeout, so a slow answer is not cut and sent again. The default limit is 120 s (before: 60 s per attempt, up to 5 attempts, about 400 s in total). A watcher failure names its cause in the log: no free background slot, or no provider answer in the time left. Measured on 2 November 2026 (live log): 17 watcher calls took 1.5 s to 54 s (median 8.4 s); her replies took 2.6 s median in the same 48 hours. At 02:15 CET two watcher attempts were cut at 60 s and the third answered after 50 s; the proxy showed the cut attempts as CANCELED. | Retries wait longer after each failure; the watcher does not cut slow answers. |

### Known open items

- **Her messages are stored twice: resolved by #34 for new messages.** The
  old copies stay until `rag_maintenance.py dedupe-self-copies --apply`
  runs.
- **Time zones: resolved by #33.** History lines, the autonomy planner and
  the current-message line all use the container time zone. Their text
  formats still differ: `[Sat ... local]` in history, `[YYYY-MM-DD
  HH:MM:SS CET]` in stored rows, and `Sun 2026-11-01 17:33 CET` on the
  current-message line.
- **Internal markers in tool results.** `__MESSAGE_SENT__` and similar
  markers reach the model in tool results and history. The
  plaintext-after-send filter reads them, and root reserves that filter.
- **Four filters reserved for root:** `_should_skip_plaintext_after_send`,
  `_prepare_tool_params`, `_TOOL_ALIASES` and
  `_extract_stickers_from_text`.
- **The `tool_` prefix repair.** `normalize_native_tool_calls` removes a
  leading `tool_` from a tool name. This is a name repair like
  `_TOOL_ALIASES`.
- **Partial batch results.** Dame Curie made a request in the test
  channel on 1 November 2026 (session record). When one native call in
  a batch fails, mark the calls in that batch that succeeded. Then she
  does not run a live call twice.
- **Rows the REM backfill moved before #24** keep their last
  `created_at`. New messages are stored after them; no restart moves
  them again.
- **The custom JSON tool protocol** (`CUSTOM_TOOL_CALLS`) parses calls
  only from streamed responses. It is off while native calls are on.
- **Word triggers that remain.** An inventory on 1 November 2026 found
  9 places that act on words in her output and 13 that act on words in
  user input. Root decides each one. Examples:
  - `_extract_stickers_from_text` sends a sticker when a sticker name is
    a word in her reply.
  - `_needs_up_to_date_info` runs a web search before the model call on
    words in the user message.
  - `VISUAL_REFERENCE_RE` attaches earlier images on words such as
    "image" or "look at".
  - `_sensitive_context_text` marks a stored fact private on words such
    as "password". This is security policy.
- **An error in a progress update before the tools: resolved by #34.**
  The progress update writes no memory row now. A Discord send error stops
  it with the cause from #26. An error in its text formatting still
  propagates and stops the turn.
- **The embedding error log names only the exception class**
  ("Embedding failed: <class>", `_embed` in `rag_memory.py`). AGENTS.md
  says an error message names what failed and why.
- **Embedding cost.** One 6,000-character piece takes about 7 s on the
  CPU embedder (measured live on 1 November 2026, not in the
  repository). `_split_embed_chunks` makes pieces of up to 6,000
  characters with a 200-character overlap. A fetched web result of up to
  12,000 characters is three pieces, about 21 s (estimated from the one 7 s measurement; not measured as a whole). A user message row
  embeds up to 8,000 characters (`add_to_channel_memory` in
  `rag_memory.py`): two pieces. Since #31, `bot_output` rows (her replies
  and tool records) are not embedded.

## Publisher inventory update - 2026-10-03, 19:44Z

The initial repair below restored publication but continuously ran rsync across all
sites. The follow-up replaces that loop with one short-lived remote inventory command.
It compares cached metadata first, verifies changed content only when needed, and queues
only differences. Local edits still use inotify. Unchanged checks no longer emit per-site
success messages. See [Publishing](PUBLISHING.md) for the algorithm and scale limits.

Installed at **19:44:53Z**, service PID **676081**. Its first normal background inventory
reported **31 targets, 31 cold content checks, zero repairs**. A subsequent **65-second
read-only process observation** saw **two SSH commands, 30.6 seconds apart, and zero
rsync processes**. No synthetic source edits or remote deletions were used.

Independent `gpt-6-astra` reviewed the implementation and the final correction. Its two
liveness findings (one unstable site blocking every audit; dirty work starving remote
repairs) were fixed before deployment. Council source inspection supplied the short-lived
receiver/stdin protocol precedent; its full-file hashing and incompatible publication
policies were not copied. Remote Python is 3.12.3; local operator Python remains 3.14.4.
Syntax/diff checks passed. No tests ran. This is not measured 50,000-site acceptance;
request size, full metadata traversal and whole-audit timeout limits remain explicit.

Private previous-source/state backup:
`/var/backups/dame-curie-v2-recovery/publisher-inventory-20261003T194453Z`.
This update is deployed locally, not yet integrated into PR3.

## Publisher repair - 2026-10-03, 19:14Z

The publisher was in a restart loop. Read-only remote inspection found
`hammered-wallet` missing; both remote roots and the other 29 saved site markers/identities
matched. Service-mode synchronization skipped claim when a saved site identity existed.
The resulting transfer failure stopped the whole publisher.

The focused repair is installed in `/opt/dame-curie/scripts/publisher/{guard,mirror,service,transport}.py`.
Root explicitly confirmed local-to-remote authority, including empty recreated remote
roots and stale remote replacements. The service now refreshes destination identities,
reclaims each transferred site, reconciles remote state on periodic scans, and retains
failed transfer/deletion work without stopping other sites. Errors identify the operation,
site, exit code and available guard/transport cause. Filesystem and SSH checks remain.

At deployment, **19:14:11Z**, service PID **643148** started. Subsequent read-only comparison
confirmed **18 local files and 18 remote files in `hammered-wallet`, all SHA-256 hashes equal,
with no missing or extra files**. Recovery was performed by the background service, not
`--once`. The service remained active with **zero restarts**; later sites also completed.

Independent `gpt-6-astra` source review found a missed-deletion retry bug in the first
patch; it was fixed before deployment. Final source review found no remaining blocker.
Syntax/diff checks passed. No tests, synthetic file edits, remote deletion drills, V1
startup or bot deployment ran. Full remote-root destruction recovery is source-reviewed,
not exercised. This repair is local and deployed; it is not yet included in PR3.

Private pre-repair source/state backup:
`/var/backups/dame-curie-v2-recovery/publisher-repair-20261003T191411Z`.

## Earlier production state

At **17:55:02Z**, the coordinator confirmed canonical Dame login **1545541390392369165** on the image below. Temporary Dirac is not the current production target. These are coordinator-supplied facts; the publication worker did not access private state.

- Source: `306b4138540c0dd40b5de8c145b1c61337255405`.
- Image: `sha256:778f5dc420c46de0e2d21b42410bca6a571b15896d64ffe99ac5b3cc3155f618`.
- Container: `01ce0313bac814cdae84b5b6dbc93ada5cefd1101bc1c0f920619e1348f8f6a0`.
- Started: `17:52:44.365556213Z`. Running, restart count `0`. Actual login observed.
- No startup traceback, auxiliary-profile error, or context-extraction error in the inspected last 600 log records.
- Saved deadline: `1800` seconds. Attempt-limit key absent.

This is passive production observation, not a new test or proof of every feature.

The first deployment failed because `/app/build_provenance.json` had mode `0600`. The coordinator rebuilt with `COPY --chmod=0644`. Source `eb16880` then logged in but failed context extraction. The narrow blank-role resolver correction is included in current source `306b413`; it does not resolve complete distinct-role support.

The coordinator preserved both 13-file site trees and corrected the original publication. Root later deleted the remote `hammered-wallet` directory. The existing publisher `--once` recovered it. Saved and remote identity `[2314,17193851138]` and the ownership marker match. The HTML and nine known image hashes match the retained source. Publisher service is active, PID `559306`, restart count `0`. No new refresh tool was implemented.

Root approved removal of exactly 12 unsupported live settings. The coordinator removed those at `17:36:45Z`, preserved all other fields, and retained a private backup.

## Publication and validation limits

[PR3](https://github.com/donpimponnousacondom-afk/dame-curie/pull/3) contains the source and later documentation-only corrections. Independent Luna/max and Sol/high reviewed the final source deltas. Full base-to-head coverage remains incomplete. The pull request is ready for human review, not merged; root owns merge.

Root deferred tests. No tests or synthetic messages were run for this deployment. Earlier source `23f0560` had **4,334 passed, 48 subtests passed, and two failures**. That is not a passing result for the deployed source. The observed startup and login do not establish full feature acceptance. GitHub has no checks; absence is not a pass.

Two issues remain open:

1. Complete distinct-role AUX/autonomy profiles remain restricted. The all-empty selector correction is deployed, but it does not resolve that role contract.
2. The publisher's legacy `curie` marker namespace is not covered by `static.htaccess`. This remains a separate policy question. No restriction was changed; remote exposure is unverified.

The P3 image-guidance wording issue is deferred. Generated-image URLs remain valid. No new image behavior was added.

## Historical record - 2026-09-25

**Everything below records the earlier temporary Dirac release. It is preserved as history, not current runtime state or current authority.**

## Closure and release state

**Round-two corrections and documentation retirement are complete. Corrected source `89fb851` is live on temporary Dirac.** The coordinator exercised root's delegated temporary-only decision after source/QA/artifact checks and one bounded smoke case. Canonical/V1 activation, publisher/shared-service lifecycle changes and remote operations remain held. This is not standing permission for future agents to repeat runtime operations.

Start with the [closure receipt](../audit/20260924T210402Z-audit/09-CLOSURE.md). [AGENTS](../AGENTS.md) preserves authority/boundaries; [Operations](OPERATIONS.md) covers recovery; [TODO](../TODO.md) distinguishes completed work from held decisions. Internal independent closure is not a replacement sign-off by the original external auditor; its conditional verdict and originals remain unchanged.

## Source and QA

| Checkpoint | Evidence |
| --- | --- |
| `eb188ac` | External round-two verdict/five follow-ups preserved verbatim |
| `c2d6b0e` | Provider reservation/incident, autonomy actor/logging and taskless-smoke corrections; QA70:345 focused passes |
| `89fb851` | Prompt/catalog/native-call/media/follow-up/readback corrections and existing-case adaptation; final QA source/test blobs match |
| QA75/76 tree`511a355fabe792cc6ae844d26004de7c55c104b4` |92focused passes and selected Ruff F821/F822/F823; **3993passed+28subtests** in the full safe suite |
| `f815857` | Consolidated guides, root-confirmed audit rename,39phase and28internal-note retirements; only Python edits are two operator-docstring pointers |

QA used Python3.14.4, synthetic configuration/state, network-none and no private mounts. The safe suite excludes `tests/test_streaming.py` and `tests/test_streaming_primary.py`; it is not unrestricted/live-provider testing. Counts overlap, do not sum. The catalog-loop case uses padded synthetic descriptions and fake dispatch/initial assembly while exercising real expansion/loop/budget logic, not production schema-size or full transport acceptance.

Exact commands, failures, corrections and immutable evidence refs: [validation](../audit/20260924T210402Z-audit/validation.md). Finding dispositions: [response](../audit/20260924T210402Z-audit/05-IMPLEMENTER-RESPONSE.md). Original conditional verdict: [round two](../audit/20260924T210402Z-audit/08-ROUND2-REPORT.md).

## Verified and deployed artifact

Image **`sha256:a466208179d1cccd2cb4c1ef93486f6c5d408d4e5d812becf725a39479a070cc`**, local tag`dame-curie-app:89fb851`, source revision`89fb851144dbd9c0bd661a67c5937161d1b58b52`.

QA77 built an explicit offline source overlay onto previously verified `be28b85` image`sha256:3136eef90508aa395217b8d21dc8deafda55354f00585071776fffb7ca6f6214`, because the local Python-base tag was absent. No pull/install; normal recipe and dependency lock unchanged, dependency layers inherited, **not freshly rebuilt**. QA78 matched all56copied inputs to the committed archive and checked baked commit/branch/dirty plus OCI revision. The existing guarded constructor passed in the actual image without network/private state/login. Later documentation commits do not change its application inputs.

## Current temporary runtime - checked16:47:48Z

- Account`dame-curie`, UID1005; rootless engine`12fb714d-4e16-45ad-bb31-a86fb1a5ee8d`, socket`/run/user/1005/docker.sock`.
- Container **`ef618129341ed4b2b83dceebd2a92e3e0e3437585e53f96c488381a3ca23e2d5`**, running the immutable image above; started**16:46:31.285765518Z**. Durable image selector matches.
- Fresh startup evidence verified Discord identity**1504398705539944560** at**16:46:35.602714316Z**. Embedding readiness passed; pending smoke list empty. Docker status alone was not used as identity proof.
- Request**`857116de560f4054b261202d7272dcab`** completed in **7seconds**, one delivery, exact21-character marker body plus configured29-character footer, zero readback failures. It ran on the immediately prior smoke-scoped container using the **same immutable image**, not on the final recreated container. No second inference was submitted. This is happy-path acceptance, not a failure/feature matrix.
- Original controls restored **byte-exact**, including all three allowed channels. Low reasoning/output12345/REMoff/autonomy-control-off/RAGon and image qualityhigh preserved; neither image alias disabled. Profile, REM, prompt and smoke-config fingerprints unchanged. One stored server prompt1939UTF-8 bytes, none over16KiB; external prompt mount verified, base personality uninspected.
- Coordinator mistakenly requested `restart` after stopping the smoke candidate; the operator correctly refused, exit1. Evidence was preserved privately, then approved `start --replace` recreated it with original controls. This invocation error remains in the ledger; no source bypass or repeated smoke was used.

Rollback: retained old image`sha256:5e3ed07db29a275263c7454fb75510142264cb269db3563a591a6085137dc51f` (source6859025), root-only evidence`/var/backups/dame-curie-dirac/round2-release-20260925T163646Z/`. Future rollback is image-only under a compatible grant; do not overlay these dated controls on later human edits. Keep each smoke request with its terminal receipt. Host viewer/Screen were **not** updated/exercised; installed operators still match reviewed89fb851 logic, not later docstring edits.

## Retained decisions and limits

Reasoning-only terminal/fallback and mandatory tool-reasoning policies remain unchanged pending root. Shell remains admin-or-allowlisted with same-UID writable-control trust explicit. Viewer oversized-record/redaction-continuity loss stays fail-closed until viewer restart, including affected canonical interactive paths; source is not host-installation evidence.

C09 import-time dotenv redesign is an accepted deferral, not an open task. P08/I05 historical provenance is permanently unattributable and quarantined, with no cache cleanup. Canonical native-image reconciliation remains held; its private profile was not inspected. Voice, exhaustive media/admin/plugin/provider combinations, replicas, sustained load and publisher remote-deletion recovery remain unverified. Jobs do not resume workers after restart; runtime footer markers are not authentication. Ordinary shared embedding requests are permitted and occurred; no shared-service lifecycle/configuration change followed.

## Documentation and history

Current guidance is README/AGENTS/SECURITY/TODO plus the nine guides. `f815857` retired39unchanged phase files and28unchanged internal notes after migration/recovery preservation. All16external originals remain byte-identical to `eb188ac` in root's renamed audit directory; response/validation/closure, quarantine/process companion, QA recipe and failed-QA evidence remain.

`git show eb188ac:phase-II_v2/SESSION_LOG.md` recovers the verbatim prior grant; that revision retains all phase files. Internal notes remain in`89fb851` under the original audit path; list its Git tree to recover them. These are historical evidence, not renewed operating instructions. Earlier status is recoverable at`ab64853:docs/STATUS.md`.

All existing refs/worktrees/caches remain. Historical inventory26worktrees/25branches/22checkpoint refs and86commits (54equivalent/32non-equivalent across13families) is dated mapping, not current counts/cleanliness proof. Five new QA evidence refs preserve intermediate/final trees. Root's unrelated ignored audit material, `reports/` and skill work remain untouched.
