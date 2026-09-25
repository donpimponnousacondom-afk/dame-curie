# Micro-lane: stale fetch_url cases reconciled

Temporary evidence. Source-only pass; no interpreter, tests, lint, import or network.
Not permanent architecture or operating authority.

## Selected network contract (coordinator decision)

`bot_tools.py` keeps its current HTTP(S)+hostname validator, **including private/local
URLs**. It is a URL-shape check, not an SSRF isolation boundary. No source
network-policy change was authorized or made.

- `_is_safe_url` (`bot_tools.py:456`): accepts `http`/`https` with a hostname;
  returns False for other schemes and missing host. Docstring already says
  "including private networks".
- `_fetch_public_url` (`bot_tools.py:5617`): re-validates every hop before each
  `session.get`; invalid hop raises `ValueError("URL must use HTTP(S) and include
  a hostname")` (`:5633`). Redirect target is `urljoin`ed (`:5647`).
- `FetchUrlTool.execute` (`bot_tools.py:5687`): empty url → `"Error: url is
  required"` (`:5695`); `_is_safe_url` false → `"Error: URL must use HTTP(S) and
  include a hostname"` (`:5697`), returned before any session/network work.

## Changed file

`tests/test_fetch_url.py` only (134 → 141 lines). Exactly three existing cases
adapted; no new tests, functions, helpers or try/except. `FakeResp`, `FakeSession`,
`_Content`, `_run` untouched and reused.

Module docstring (line 1) was stale: it claimed "SSRF-safe redirects, private URL
refusal". Replaced with the surviving contract, including an explicit statement
that the validator is not an SSRF boundary. Docstring is now 6 lines.

## Case mapping (old → new)

| Old selector | New selector |
| --- | --- |
| `test_is_safe_url_blocks_private_and_allows_public` | `test_is_safe_url_accepts_http_s_and_rejects_other_schemes` |
| `test_fetch_url_refuses_private_without_network` | `test_fetch_url_rejects_invalid_scheme_before_network` |
| `test_fetch_public_url_refuses_redirect_to_private` | `test_fetch_public_url_refuses_invalid_redirect_hop` |

No selector above survives under its old name; no additional case definitions exist.

## Coordinator correction after handoff

The bare-bot rationale below is insufficient: `_get_shared_session` is module-level, not a bot method. Coordinator added an `AsyncMock` that fails on session acquisition plus `assert_not_awaited()` to the existing direct-refusal case. No real I/O is possible in that case even on regression. The three one-to-one renames remain the only changed test definitions; no extra case/helper was added.

## What each adapted case now asserts

1. **Validator shape.** `https://example.com/page` accepted; `http://127.0.0.1/`,
   `http://localhost/admin`, `http://10.0.0.5/x` and `http://169.254.169.254/latest`
   are now asserted **True** (were False). `file:///etc/passwd` and `http:///no-host`
   (no hostname) remain False.
2. **Invalid direct request.** `FetchUrlTool(SimpleNamespace()).execute(msg,
   url="file:///etc/passwd")` returns the exact refusal string. The bot is a bare
   `SimpleNamespace` with no `_get_shared_session`, so any reach into a session or
   network would surface as a different error rather than that string.
3. **Invalid redirect hop.** Start `https://ex.com/jump` answers `302` with
   `Location: file:///etc/passwd`. `ValueError` must mention `HTTP(S)`, and
   `session.calls` must be exactly `["https://ex.com/jump"]`, i.e. the second
   request is never issued. The session records the URL on `get`, so the
   assertion is a direct call-count check.

## Preserved

`test_fetch_public_url_follows_redirects` and
`test_fetch_url_returns_page_text_after_redirect` were not modified: their
behaviour did not depend on the private-URL refusal.

## Not checked here

No execution, import, collection or resolution count is claimed. All URLs are
synthetic (`ex.com`, loopback literals); nothing in these cases performs real
network I/O when run, but execution is left to coordinator QA.
