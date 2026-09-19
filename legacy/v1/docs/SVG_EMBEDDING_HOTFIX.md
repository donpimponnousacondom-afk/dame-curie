# Portable SVG and embedding boundary hotfix

This patch fixes two independent consumers of image bytes. It does not change the chat model, reasoning effort, credentials, timeouts, Ollama resource limits, publisher, storage schema or original SVG files.

## Embedding boundary

Port the `rag_memory.py` changes and `tests/test_rag_media_projection.py` together.

- `_embed` projects explicit binary-media envelopes/data URIs out of the text **before** cache lookup, chunking and HTTP. Query, background storage and backfill already converge here.
- Preserve useful surrounding text, raw database content/metadata and existing clean cache keys. Do not move this transformation into the stored-content hash or rewrite history.
- Strip complete image/audio markers and EOF-truncated payloads; the latter occur when tool memory is capped before its closing marker.
- A pure-binary projection makes no embedding request.
- For Ollama `/api/embed` only, an exact HTTP400 `the input length exceeds the context length` splits the rejected chunk by Unicode codepoint. Splits are depth-bounded, retain all text and never cache a partial result or cool down the whole endpoint for this input-specific rejection.
- Other failures retain the existing failure policy. This is not a general retry increase or a larger timeout.

Existing already-populated contaminated vectors remain intact. No global backend-ID change or automatic mass re-embedding is introduced. Historical cleanup would be a separate, explicitly scoped operation. Pure-binary raw records may remain pending under existing eligibility rules, but do not generate HTTP work.

## SVG and vision boundary

Port `image_media.py` plus its integration changes in `bot_tools.py`, `providers.py` and `bot.py`, and the focused SVG/media tests.

- `fetch_url` returns SVG source as readable XML, rather than manufacturing a vision attachment. Existing ordinary HTML fetching must keep its text-extraction behavior.
- Actual visual inspection converts SVG to PNG. Raster MIME labels are derived from their byte signatures instead of blindly treating legacy images as PNG.
- The provider boundary handles new media and existing data-URI image parts on a copied request. Original files, history and cached source bytes remain unchanged.
- Conversion failures become explicit model-facing media feedback rather than an invalid image submitted to the upstream provider.
- Rendering has bounded dimensions, memory, CPU time and wall time, with subprocess cleanup. External resource/entity handling must remain constrained; reading SVG source as text does not execute or render it.

The Curie image already contains ffmpeg's `librsvg` decoder. No new Python package is required. Verify this capability on another installation:

```sh
ffmpeg -hide_banner -decoders
```

The decoder list must contain `librsvg` for SVG visual inspection. Copy `image_media.py` into the application image; `docker/app.Dockerfile` includes that addition. A renderer-unavailable error must not fall back to sending SVG/XML as PNG.

## Acceptance and rollout

Use Python3.14 and synthetic state. Test both text/source and actual raster-output behavior, provider payload MIME, preserved input/history, invalid/external SVG rejection, subprocess cancellation, truncated binary markers and bounded Ollama context recovery. Do not run tests against live bot memory or make paid provider calls as fixtures.

Current measured tests, runtime baseline, deployment evidence and rollback location are recorded in `docs/STATUS.md`. Existing source has unrelated baseline failures; distinguish those from new regressions rather than reversing unrelated local changes.

This is code-only behavior repair, not a data migration. Code rollback selects the previous image. Do not restore an older memory snapshot as a routine code rollback: that would discard newer history.
