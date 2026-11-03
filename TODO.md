# Open items

## Dirac retirement, left for root

- [ ] Revoke the Dirac bot token, or delete the Dirac application, in the Discord developer portal. Deleting its config file on the host did not revoke the token.
- [ ] Check whether the Dirac publisher left site copies on a remote host. Not verified.

## Remove the local Ollama embedding service when root says so

- Root, 2 November 2026: "Turn it off, but don't delete it just yet, just unplug the wire from the whole harness and leave it as side note to remove in the future".
- Live state since 2 November 2026, 19:17 UTC: `DAME_CURIE_EMBED_MODE=external` in `/srv/dame-curie/deploy.env`. With this value, `scripts/instance.py` adds the overlay `docker/compose.embeddings-external.yaml`.
- The bot embeds with OpenAI `text-embedding-3-large` at 1536 dimensions (#42).
- The `dame-curie-ollama-1` container is stopped, not removed.
- Kept: the image `ollama/ollama:0.40.13`, the volume `dame-curie_ollama-models`, and the `ollama` and `ollama-pull` services in `compose.yaml`.
- [ ] Removal, part 1 (host): delete the stopped Ollama containers, the volume and the image.
- [ ] Removal, part 2 (one PR, first change): remove the two services and the `embeddings` and `model-download` networks from `compose.yaml`.
- [ ] Removal, part 2 (same PR, second change): fold the external overlay into the base `bot` service. Remove its `depends_on`, the local mode, the local base URL and the `embeddings` network. Then update the modes in `scripts/instance.py` (`EMBED_MODES`, `owned_config_files`) and their tests.
- To plug Ollama back in, step 1: set `DAME_CURIE_EMBED_MODE=local` in `/srv/dame-curie/deploy.env`. The mode is not read from `bot.env`.
- Step 2, in `/srv/dame-curie/config/bot.env`: `DAME_CURIE_EMBED_BASE_URL="http://ollama:11434"`, `DAME_CURIE_EMBED_MODEL="qwen3-embedding:0.6b"`, `DAME_CURIE_EMBED_DIM="1024"`, and blank `DAME_CURIE_EMBED_API_KEY` and `DAME_CURIE_EMBED_REQUEST_DIMENSIONS`.
- Step 3, in the same file: set the four `DAME_CURIE_RAG_*_SIMILARITY` cut-offs blank. Blank gives the Qwen values 0.35, 0.40, 0.40 and 0.85.
- Step 4: run `instance.py dame-curie up`.
- Cost of plugging back: every stored vector carries the OpenAI backend tag at 1536 dimensions. Search reads only vectors of the configured backend, so recall finds no row until that row has a Qwen vector. If Qwen returns, add its query instruction; see the note in [docs/OPERATIONS.md](docs/OPERATIONS.md).
- The catch-up pass embeds for at most 60 s every 10 minutes. A manual `rag_maintenance.py backfill` runs without the 10-minute gaps. Its time on Qwen: not measured. On OpenAI, 6,247 row attempts took 24.5 minutes (#42).

## Behaviour

- [ ] Partial batch results. When one native call in a batch fails, mark the calls that succeeded, so she does not run a live call twice. Dame Curie asked for this on 1 November 2026.
- [ ] Tool-call batching, remaining part: the Codex and Claude Code partition (read-only calls in parallel, mutating calls serial in order). Today every call in a batch starts at once, but `shell` takes one bot-wide class lock, so batched shells run serially and one long shell blocks shells in every channel.
- [ ] Recall can duplicate rows that are already in the current-channel transcript.
- [ ] The automatic web search runs on the smoke-task preamble text and stores junk web results.
- [ ] Word triggers that remain: 9 places act on words in her output and 13 on words in user input (inventory of 1 November 2026). Root decides each one. The list is in the known open items of [docs/STATUS.md](docs/STATUS.md).

## Repository

- [ ] Old `compose.yaml` Ollama tuning comments go with the Ollama removal above.

## Held by root, not tasks

- Reasoning-only terminal responses stay terminal without automatic fallback.
- The mandatory tool `explanation` argument stays.
- Same-UID shell trust stays explicit; separating the control files is root's decision.
- Four filters are reserved for root: `_should_skip_plaintext_after_send`, `_prepare_tool_params`, `_TOOL_ALIASES` and `_extract_stickers_from_text`.
