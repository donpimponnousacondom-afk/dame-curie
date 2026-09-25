# Image generation and editing

One model-facing tool: `image_generator`. Generation and editing share one operator-configured native Images endpoint and credential. Image configuration is restart-only; chat-provider reload does not apply it.

## Configuration

Use exact IDs accepted by the configured gateway, including any provider namespace. A valid credential does not make an unqualified model alias valid.

```dotenv
IMAGE_GEN_PROTOCOL=images
IMAGE_GEN_BASE_URL=https://images.example.invalid/v1
IMAGE_GEN_API_KEY=
IMAGE_GEN_MODELS='{"provider/model-a":"Normal image tasks","provider/model-b":"Prefer for detailed generation and edits"}'
IMAGE_GEN_MODEL=provider/model-a
IMAGE_GEN_QUALITY=low
IMAGE_GEN_TIMEOUT=300
```

The hostname and model IDs above are placeholders, not working defaults.

- `IMAGE_GEN_MODELS` is a JSON **object** mapping exact model IDs to non-empty descriptions. It is not an array. Descriptions are operator selection guidance, not evidence of provider capabilities.
- `IMAGE_GEN_MODEL` selects the default and must be a key in that map. An explicit nonempty tool-call model must also be an exact key; an empty model argument uses the configured default. There is no guessed alias, built-in model choice or automatic fallback.
- `ENABLE_IMAGE_GEN=auto` registers the tool only with a native protocol, nonempty endpoint, valid nonempty model map and listed default model. Explicit `true` cannot force an unusable profile on; explicit `false` keeps a usable one off. Missing, malformed or stale image settings disable only image generation, not unrelated bot startup. `IMAGE_GEN_CONFIG_ERROR` and the image feature status name the setting to fix without printing its value. A direct image-tool call against a disabled profile refuses before HTTP.
- Blank `IMAGE_GEN_API_KEY` means no bearer token; it is valid for a configured keyless endpoint. Images never inherit chat endpoint/key settings.
- `IMAGE_GEN_QUALITY` defaults to `low` in code and both templates. The tool's optional `quality` overrides it; an empty quality argument uses the configured default. Accepted values are provider-specific. Model descriptions do not automatically change quality.
- The native Images protocol is the only route. The separate HD profile and old Pollinations/chat-completions image routes are retired.

Configured model choices and descriptions are exposed in the tool's dynamic schema, including the exact-ID enum. They are not fetched from a provider catalog on each call.

## Tool calls

```text
image_generator(prompt="…")
image_generator(prompt="…", model="provider/model-b", quality="max")
image_generator(prompt="Change only the background", image="https://example.invalid/input.png")
image_generator(prompt="…", image=["/allowed/image-a.png", "/allowed/image-b.png"])
```

These illustrate arguments, not verified provider quality values or readable local paths.

- No resolved references: submit to `/images/generations`. Pass `image=""` (or an empty list) to request generation from scratch even when the triggering message has image attachments. Only `image=None`/omission falls back to those attachments.
- Resolved references: submit to `/images/edits`, preserving original reference bytes rather than adding native-path downscaling. Large edits can take longer or cost more than reduced inputs.
- References retain the existing URL, local file, inline data URI and list handling. At most four references are used; additional ones are truncated.
- Local paths resolve symlinks before enforcing the existing generated-image/`temp` path restrictions; a symlink escaping those roots is refused. This changes neither local authoring nor the independent publisher. HTTP(S) inputs retain the existing behavior, including private-host acceptance and refusal to follow image-input redirects.
- Network/local reference reads retain the existing 20 MiB limit. The inherited inline-data-URI path does not enforce that same byte limit; consolidation does not claim to fix it.

## Delivery and failures

`auto_send=false` is the default: save the image and return its local/public references without posting it. Present the saved result with existing file/media tools or its image-preview URL.

`auto_send=true` posts once. `__IMAGE_SENT__` means it was already delivered; do not resend it. If save-only persistence fails, the tool does not silently upload instead. Generation failures, ambiguous responses and delivery failures do not trigger an automatic second generation request.

Submitted prompts, existing image sidecars, request-log correlation and media concurrency handling are retained. Website public URL settings do not redefine the separate image archive URL mapping. Publisher behavior is unchanged.

## Migration

Before canonical activation, the coordinator must reconcile that instance's private effective `IMAGE_GEN_*` settings and `ENABLE_IMAGE_GEN` with this native-only contract. The historical profile migration for the temporary instance does not establish canonical settings. Replace split profiles with one `IMAGE_GEN_*` block and a configured model map; remove retired image-profile settings from the target instance while preserving all unrelated settings and credentials. Keep the working endpoint/key, use provider-advertised exact model IDs, and make previous per-profile quality choices explicit through the optional tool argument when needed. Do not copy an entire other instance's environment file. Disabled image generation is safe for unrelated startup, not proof the migration is complete.

The last recorded temporary runtime used quality `high` with a 600-second timeout; that is dated runtime evidence, not a fresh observation or the new source default. An explicit private quality setting is preserved; an omitted setting uses the new `low` default after restart. Verify that choice during the authorized migration/acceptance rather than assuming an unchanged default.

The old `hd_image` execution name is retired; use `image_generator`. The coordinator must check private `disabled_tools` separately for that name before acceptance. This document specifies the source contract. Deployment and actual provider acceptance must be recorded separately in [STATUS.md](STATUS.md); a successful model-catalog lookup is not an image-generation/edit acceptance test.
