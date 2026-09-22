# Discord sub-agent jobs and progress threads

Lane `work/dirac-discord-jobs`, worktree `dirac-discord-jobs`, base `7b4398c`. Source-only: no
runtime, private configuration, credential, Docker, log or network access was used. Parent owns
final integration and the live exercise.

Owned paths: `jobs.py`, `job_routing.py`, `bot.py` job/thread sections, `bot_tools.py`,
`tool_schemas.py`, `tool_prompts.py`, `response_observability.py` (added for the observer hook),
focused job/thread/observability tests, this file. Untouched: `compose.yaml`, `config.py`,
`docker/**`, `scripts/publisher/**`, shared ledgers, `docs/**`, `autonomy.py`,
`message_pipeline.py`.

## What already existed (read, not rebuilt)

- `!bg [--provider main|autonomy|aux] [--model MODEL] -- GOAL` in `bot._handle_command`; the
  model-facing `spawn_background` tool; routing in `job_routing.py` (same-role base URL/model/key
  only, never endpoints or keys from the model, configured fallbacks preserved).
- The detached worker in `jobs.run_background_job`: extended budgets, `_acquire_ai_slot` with
  `priority="background"`, real tool loop through `_build_openai_tools` / `_native_calls_from` /
  `_recover_text_tool_calls` / `_dispatch_tool_calls`, a job-owned provider closed in `finally`,
  and restart cancelling rather than resuming in-flight records.
- Canonical prompt assembly in `jobs.background_messages`: `bot._get_personality()` plus
  `bot.memory.get_server_prompt(message.guild.id or "DM")` plus `bot._tool_system_prompt(...,
  message=origin)`. A thread origin is in the guild, so this was already the origin server's prompt;
  the job's origin was deliberately **not** re-pointed at the new progress thread.
- Lifecycle: owner/admin cancel (`!job cancel <id>`, `!stop job <id>`), `!jobs` guild listing,
  status/result persistence, delivered-result mention in the origin channel.

No parallel job framework was added.

## Defects fixed

1. **Thread target (`jobs.py`).** `Message.create_thread` posts to
   `start_thread_with_message(self.channel.id, ...)` and every `Message` exposes `create_thread`, so
   a job started inside a thread called `POST /channels/{thread}/threads` and the old
   `elif hasattr(channel, "create_thread")` rescue could never run. The origin channel is now
   classified explicitly with `isinstance(channel, discord.Thread)` — the SDK's own idiom — and such
   a job creates a standalone public thread in the origin thread's own parent channel. A thread whose
   parent cannot be resolved is reported, not guessed at. The origin-message path runs exactly as
   before for every channel that is not a thread. Test fakes bind this by monkeypatching
   `discord.Thread`, not by duck-typing their way past the discriminator.
2. **Honest thread failure (`jobs.py`).** Creation failure was only `logger.info`; a created-but-
   unwritable thread was swallowed in `_post_thread`. Both now record `thread_error` on the job
   (new persisted field, default `""`, old records load unchanged) and post one line in the origin
   channel, gated by the same `error_replies` control as every other job notice. The wording states
   what happened and what still happens ("there is no progress thread (<reason>). The job continues;
   its result lands here."): a failed first post is recorded as `initial progress post failed`, not
   as a permanent inability to post, and that thread is not retried for this job. `thread_id` is
   cleared when a thread carries no progress, so nothing links an empty thread. Direct-message jobs
   stay quiet because threads are impossible there, not merely unavailable.
3. **Recursion guard (`jobs.py`).** `orig_message._bg_job = True` was the only guard, and the
   approved SDK copy declares `__slots__` on `Message`, so the write could not be relied on. A
   message-id marker is not the answer either: the origin message is shared with the live turn that
   started the job, so a marker made the live turn's own second attempt look like a nested job and
   told the model to do the long work inline. The guard is now `jobs.JOB_TURN`, a ContextVar set
   around the job's own tool loop: the job task and every tool subtask it spawns see it, the live
   turn's task does not. A live turn that asks again still gets the requester's real limit
   (`ALREADY RUNNING`, ack and stop), and a job's own turn gets `ALREADY INSIDE`. No manager state and
   no message attribute is involved.
4. **Thread association and allowlist (`bot.py`).** `!job <id>` now appends the progress-thread link
   built from the job's own guild/thread ids, or the recorded `thread_error`. `allowed_channels` is
   an exact channel-id whitelist and a thread has its own id, so a job thread (and any follow-up in
   it) was dropped once an allowlist was configured; `_channel_allowed` now lets a thread inherit
   its parent channel's allowance in both gates (`on_message` and `_message_update_allowed`). This
   is fail-closed and inert while `allowed_channels` is empty, its current default. Autonomy's own
   gate still lists channels only.

## Provenance of the SDK claims

SDK: **discord.py-self 2.1.0**, read from the frozen 734c050 image. Approved copies and line
references:

- `/tmp/curie-sdk-public-u5v2n7g8/message.py` and `abc.py` (first capture).
- `/tmp/curie-sdk-dirac-k2y3w7f0/channel.py`, `threads.py`, `mixins.py` (coordinator's second
  capture). All three questions this lane had flagged as unverified are answered there, and the code
  needed no change:

- `TextChannel.create_thread` (`channel.py:839`) is
  `(*, name, message=None, auto_archive_duration=MISSING, type=None, reason=None, invitable=True,
  slowmode_delay=None)`. Its body (`channel.py:903-913`) sets `type = ChannelType.private_thread`
  when `type is None`, then, **when `message is None`**, calls
  `start_thread_without_message(self.id, name=..., auto_archive_duration=..., type=type.value, ...)`;
  otherwise `start_thread_with_message(self.id, message.id, ...)`. So the parent-channel progress
  thread — `parent.create_thread(name=..., auto_archive_duration=60,
  type=discord.ChannelType.public_thread)` with no `message` — is the SDK's supported shape, and the
  explicit `type` is what keeps it a public thread instead of the private-thread default.
- `Thread.parent` (`threads.py:236-241`) returns
  `Optional[Union[TextChannel, ForumChannel]]` via `self.guild.get_channel(self.parent_id)`, so it is
  genuinely optional and the "parent channel is unknown" branch is real, not defensive. `parent_id`
  is set at `threads.py:180`. `Thread` defines **no** `create_thread` (the only definitions in
  `channel.py` are `TextChannel.create_thread` at 839 and `ForumChannel.create_thread` at 2938),
  which is why the old `elif hasattr(channel, "create_thread")` rescue could never run for a thread
  origin and why `isinstance(channel, discord.Thread)` is the correct discriminator.
- `class Hashable(EqualityComparable): __slots__ = ()` (`mixins.py:42-43`), plus `PartialMessage`
  slots (`message.py:933`), `Message` slots (`message.py:1942`) and no `'__dict__'` anywhere in
  `message.py`: an SDK `Message` instance cannot take a new attribute, so the original
  `orig_message._bg_job = True` write could not have worked. That claim is now supported rather than
  inferred — although the guard no longer depends on it, because it is a ContextVar.
- `from .threads import Thread` (74): `discord.Thread` is a real public name.
- `Message.create_thread` (1384) body: `start_thread_with_message(self.channel.id, self.id, ...)` and
  `raise ValueError('This message does not have guild info attached')` when `self.guild is None`.
- `isinstance(channel, Thread) and channel.parent_id == ref.channel_id` (2086): both the thread
  discriminator and `parent_id` used by `_channel_allowed` are the SDK's own idiom.
- `getattr(self.channel, 'parent', self.channel).type is ChannelType.forum` (2533) and
  `ChannelType.news_thread/public_thread/private_thread` (942-944): `channel.parent`, `channel.type`
  and `ChannelType.forum` are real attributes. `ForumChannel.type` (`channel.py:2607-2611`) is
  `Literal[ChannelType.forum, ChannelType.media]`.
- `abc.py` 651/714/1761/2899 declare `__slots__ = ()`.

Disclosure: before the coordinator flagged it, this lane had also read
`/usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages/discord/{message,channel,threads}.py`
and `/home/codexy/.cache/uv/archive-v0/z8PskheNH7OW6BCc/discord/message.py`. Those are **not**
approved inputs and nothing rests on them: every fact above was re-checked in the approved copies.
The earlier "Message has no `__slots__`, the attribute write sticks" statement this lane sent the
coordinator was wrong (the first grep was truncated with `head -3`); the approved copies show the
opposite, and the fix removes the dependency on instance layout entirely.

Still not a source fact, and relied on only as behaviour:

- That Discord rejects `POST /channels/{thread}/threads`. That is API behaviour, not something these
  files show; what the source guarantees is that the old code sent the request to the thread's own
  id.
- A media-channel post (`ForumChannel.type` can be `ChannelType.media`, `channel.py:2607-2611`) is
  classified as a thread whose parent is not `ChannelType.forum`, so the standalone-thread call is
  attempted and `ForumChannel.create_thread` (2938) rejects the unexpected `type` keyword. That ends
  in the honest failure notice and a running job, not a silent success. Not exercised.

## Validation

- Passed: Python 3.14 `py_compile` of `jobs.py`, `bot.py`, `response_observability.py`,
  `tests/test_background_jobs.py`, `tests/test_response_observability.py` using
  `/home/codexy/deepseek/dame-curie/.venv/bin/python -I -B -X
  pycache_prefix=/tmp/dirac-jobs-validation`; `git diff --check` clean. No application module was
  imported and no test was collected or executed.
- Not run: the focused tests in `tests/test_background_jobs.py` (thread-origin parent-channel
  targeting with `discord.Thread` monkeypatched, creation-failure honesty, the `error_replies` gate
  on that notice, direct-message quietness, ContextVar recursion refusal, a live turn's second
  attempt staying `ALREADY RUNNING`, `!job` link/error line) and in
  `tests/test_response_observability.py` (input-scoped delivery reporting, inert-without-observer, a
  raising observer not costing a delivery, `_run_queued_reply` bracketing on success and on failure,
  and the no-observer forward); ruff (not installed in the permitted interpreter, and no install is
  authorized in this lane); any Discord, provider or container behavior.
- Unverified runtime edges: actual thread creation/permission in the authorized guild (the API shape
  itself is now source-verified), allowlist inheritance with a non-empty `allowed_channels`, the
  `!job` link format, and the honest-failure notice path against a real API error.

## Cross-lane interface (implemented; smoke module still cf3's)

The coordinator and the smoke lane agreed this contract; it is source-only and inert unless an
operator opts in. `dirac_runtime.py` does not exist in this repository and was not created here.

Correlation is a `ContextVar`, not a channel/time window and not task identity, because the turn's
tool work runs in child tasks:

- `response_observability.TURN_INPUT: ContextVar[str]` (default `""`) names the operator input a
  delivery belongs to.
- `MaxwellBot._run_queued_reply` is the bound `ReplyQueue` handler (bot.py, replaces the direct
  `_handle_message` bind). With no `_turn_observer` it is a pure forward. With one it calls
  `observer.start(input_id, channel_id, asyncio.current_task())` **inside the turn's own task**,
  awaits the turn, then calls `observer.finish(input_id, channel_id, returned, token)` in `finally`,
  so cancellation closes the input too.
- `record_delivery` (response_observability.py) reads `TURN_INPUT` and calls
  `observer.delivered(input_id, channel_id, message_id)` for Discord deliveries. A raising observer
  is logged and recorded, never allowed to cost a real delivery. No observer attribute means
  byte-identical behaviour.
- `run_background_job` clears `TURN_INPUT` at the top of the job task: the task inherits the
  spawning turn's context, and a detached job is not part of that turn.

Observer protocol, implemented by cf3, duck-typed by `bot.py`. All three are synchronous, must not
block, must not await and must not raise:

```python
def start(input_id: str, channel_id: str, task) -> object      # set TURN_INPUT; return the token
def delivered(input_id: str, channel_id: str, message_id: str) -> None   # ignore unknown/closed inputs
def finish(input_id: str, channel_id: str, returned: bool, token) -> None  # reset token; close input
```

Outcome semantics the smoke harness must respect:

- `returned=False`: the turn raised or was cancelled. Never a pass.
- `returned=True` with ids: the turn completed and those messages were delivered.
- `returned=True` with zero ids: the turn completed without any `record_delivery`-visible message.
  Legitimate for a silent turn (`no_response`), but a smoke request that expects visible output must
  treat this as a failure, not a pass.

**Delivery coverage is partial — do not read it as "all message creates".** `record_delivery` is
called by the main reply path (bot.py:13133, plus the progress-transition callback at bot.py:13084),
by the `send_message` tool (bot_tools.py:4924) and by message edits (bot_tools.py:1873). It is
**not** called by `SendFileTool._send_blob` (bot_tools.py:5214, `message.reply(file=...)` /
`message.channel.send(file=...)`) or by plugin-posted messages, so those creates are invisible to
`observer.delivered`. The smoke runtime observes HTTP sends for all creates; the ContextVar decides
which creates belong to which input.

Lifecycle, both inline at their only call sites, no helper methods:

- `setup_hook`, after the autonomy start: if `DAME_CURIE_DIRAC_SMOKE_CONFIG` is blank nothing is
  imported and nothing changes; otherwise `dirac_runtime` is imported lazily, its
  `SmokeSettings.from_env()` and `DiracSmokeRuntime(self, settings)` are constructed, and
  `await runtime.start()` must succeed before `bot._dirac_smoke` is set. A start failure propagates
  out of `setup_hook` — an opted-in, misconfigured run must not come up looking like a pass.
- `main()` shutdown `finally`, immediately before `bot._reply_queue.close()`: the runtime is stopped
  while turns can still deliver. A stop failure is logged and never blocks shutdown.

Methods cf3 must expose: `SmokeSettings.from_env()`, `DiracSmokeRuntime(bot, settings)`,
`await runtime.start()`, `await runtime.stop()`; the runtime sets `bot._turn_observer` itself.
`bot.py` never sets that attribute and imports `dirac_runtime` only in the opted-in branch.
