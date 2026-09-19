# Active email removal

## Scope and checkpoint

- Assigned worktree: `/home/codexy/deepseek/dame-curie-worktrees/prune-email`; branch `work/prune-email-20260919`.
- Audited base: `3a71cbbc0808c24c640ccff82c265506413460d6`.
- Source removal: `1cc0e9c73b8f9d3f1a2f82d6e5698710af5c9bae` (24 files; 33 insertions, 1903 deletions).
- Source-only removal, not deployment or runtime acceptance. No main-tree edits, merge, rebase, push or additional agents.

## Deleted boundaries

- Four tools (`email_send`, `email_read_inbox`, `email_get_message`, `email_search`), mail-local SMTP/IMAP transport, MIME body/envelope parsing and argument helpers in `bot_tools.py`. Its `ssl` import had only the removed IMAP consumer. No dependency pins changed: these transports used the standard library.
- `email_inbox.py`: polling, self-copy/ignored-sender filters and poll-state implementation. Removed bot imports, construction, task scheduling, interval/reload hooks, mail credential registration and tool registrations.
- Mail configuration/feature inventory, API/default poll controls, known-tool/Telegram compatibility/result catalogs, native schemas and mail tool/prompt examples. Doctor consumes `Config.feature_report()`; no separate doctor mail implementation remained.
- Public `.env.example` and `docker/bot.env.example` mail settings; Docker COPY and allowlist entry; email in the architecture capability inventory.
- Deleted `tests/test_email_inbox.py`. Removed obsolete mail cases/imports/fixture switches from mixed tests and `deep_test_harness.py`; retained its existing generic inbox lifecycle case. No new or replacement tests.

## Protected consumers

- `InboxStore`, insert-once semantics (also used by `XMentionPoller`), JSON/locking helpers, friend/group/guild notices, read/dismiss/accept/decline, planner ordering and announcement bookkeeping remain. Only the email-specific priority, cap and renderer were removed.
- Existing generic inbox tests retain historical `email_*` fixture IDs/kinds where they exercise shared sorting, read state, invalid actions and announcement suppression—not mail transport. The obsolete email-cap case was removed.
- Shared taint/confirmation, incident handling, generic task infrastructure, URL/media intake, YouTube, TTS/images, providers, application jobs/routing, RAG/REM and publisher/site compatibility patches remain.
- X and Telegram remain. `x_client.py` is untouched: its `email.utils.parsedate_to_datetime` parses RSS dates, not mailbox traffic. Its introductory mailbox prose is historical, not active email wiring.
- Archived DNS scripts/docs, contact attribution, private configuration, mailbox contents and persisted state were not read or changed. No state migration/deletion is included.

## Changed paths

- Source: `api/state.py`, `bot.py`, `bot_tools.py`, `config.py`, `control_defaults.py`, `deep_test_harness.py`, `inbox.py`, `tool_schemas.py`.
- Public configuration/build: `.env.example`, `docker/app.Dockerfile`, `docker/app.Dockerfile.dockerignore`, `docker/bot.env.example`.
- Mixed tests: `tests/test_bot_construction.py`, `tests/test_extract_timeout.py`, `tests/test_generation_policy.py`, `tests/test_inbox.py`, `tests/test_security_helpers.py`, `tests/test_token_trim.py`, `tests/test_tool_calls.py`, `tests/test_tts_silent.py`, `tests/test_x_integration.py`.
- Documentation: `docs/ARCHITECTURE.md`; added this `phase-II_v2/EMAIL_REMOVAL.md` report.
- Deleted: `email_inbox.py`, `tests/test_email_inbox.py`.

## Source validation

- Read assigned contract/map and traced callers, registrations, shared consumers and Docker inputs; reviewed the complete diff. Vulture evidence remained candidate/historical evidence, not a general deletion mandate; no new Vulture run.
- Scoped residual searches across active Python, API, scripts, plugins, examples, Docker and public configuration found no remaining email tool/poller/transport wiring. Remaining source matches are the protected X date parser/historical prose and generic test data.
- Python **3.14.4** confirmed. All **17 modified Python files** passed standard `py_compile`, including compile-only mixed-test sources, with this prefix and explicit worktree source arguments:

  ```sh
  /home/codexy/deepseek/dame-curie/.venv/bin/python -I -B \
    -X pycache_prefix=/home/codexy/deepseek/dame-curie-worktrees/prune-email/.validation-cache \
    -m py_compile <explicit changed source paths>
  ```

- `git diff --check` and staged equivalent passed. Cache bytecode stays untracked/ignored under `.validation-cache`, outside commits. Commit hooks were disabled for these source-only commits.
- No application imports/execution, test collection/execution, dependency installation, build, Docker/service/account access, network/provider/Discord calls or private-state reads. Static compilation does not prove startup or integration correctness.

## Coordinator integration and remaining risks

1. Remove the main-only restored `web/admin/index.html` control `{ k: "email_inbox_poll_seconds", t: "int", min: 30, max: 3600 }` (coordinator reported line 1382). Web files are absent from this branch's base and were neither created nor accessed here.
2. Preserve main's identity/partner-trust fixes and `image_media.py` Docker allowlist addition. This branch touches `.env.example`, `bot.py`, `config.py`, `docker/bot.env.example`, the Docker allowlist and `docs/ARCHITECTURE.md` only for email; nearby integration hunks may conflict. No merge/conflict simulation was performed.
3. Shared STATUS/SESSION_LOG/README/AGENTS ledgers, `PRUNING_MAP.md` and dated Vulture snapshots are unchanged; coordinator owns their integration updates. Twitter/X remains a separate next cut, not part of this removal.
4. Old persisted notices/configuration or external plugins may still refer to removed mail tools. No compatibility shim or private-data cleanup was added. Old notice rows can still pass through generic inbox behavior; V2 fresh-state isolation remains coordinator-owned.
5. Builds and runtime acceptance remain unverified and require separate authority; this commit changes no deployed service or DNS/mail infrastructure.
