# Image generation and editing

One canonical model-facing tool: `image_generator`; the retired `hd_image` name is a compatibility **alias to that same tool**, not a separate HD provider/profile. Generation and editing share one operator-configured native Images endpoint and credential. Image configuration is restart-only; chat-provider reload does not apply it.

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
- `IMAGE_GEN_MODEL` selects the model and must be a key in that map. A tool-call `model` that differs from it is refused before HTTP; an empty model argument uses it. There is no guessed alias, built-in model choice or automatic fallback.
- `ENABLE_IMAGE_GEN=auto` registers the tool only with a native protocol, nonempty endpoint, valid nonempty model map and listed default model. Explicit `true` cannot force an unusable profile on; explicit `false` keeps a usable one off. Missing, malformed or stale image settings disable only image generation, not unrelated bot startup. `IMAGE_GEN_CONFIG_ERROR` and the image feature status name the setting to fix without printing its value. A direct image-tool call against a disabled profile refuses before HTTP.
- Blank `IMAGE_GEN_API_KEY` means no bearer token; it is valid for a configured keyless endpoint. Images never inherit chat endpoint/key settings.
- `IMAGE_GEN_QUALITY` is the operator's value. A tool-call `quality` that differs from it is refused before HTTP. Accepted values are provider-specific. Model descriptions do not automatically change quality.
- The native Images protocol is the only route. The separate HD profile and old Pollinations/chat-completions image routes are retired.

The tool description names the configured model and its description. The tool schema has no `model` or `quality` argument. Nothing is fetched from a provider catalog.

## Tool calls

```text
image_generator(prompt="…")
image_generator(prompt="Change only the background", image="https://example.invalid/input.png")
image_generator(prompt="…", image=["/allowed/image-a.png", "/allowed/image-b.png"])
```

These illustrate arguments, not verified provider quality values or readable local paths.

- No resolved references: submit to `/images/generations`. Pass `image=""` or **`image=[]`** to request generation from scratch even when the triggering message has image attachments. Only `image=None`/omission falls back to those attachments.
- Resolved references: submit to `/images/edits`, preserving original reference bytes rather than adding native-path downscaling. Large edits can take longer or cost more than reduced inputs.
- References retain the existing URL, local file, inline data URI and list handling. At most four references are used; additional ones are truncated.
- Local paths resolve symlinks before enforcing the existing generated-image/`temp` path restrictions; a symlink escaping those roots is refused. This changes neither local authoring nor the independent publisher. HTTP(S) inputs retain the existing behavior, including private-host acceptance and refusal to follow image-input redirects.
- Network/local reference reads retain the existing 20 MiB limit. The inherited inline-data-URI path does not enforce that same byte limit; consolidation does not claim to fix it.

Incoming-attachment controls, image-reference limits and outgoing upload limits are separate. SDK attachment reads may buffer before actual-byte checks; these checks are not a hard transfer/RSS bound or proof of Discord's account/channel allowance. Raising a media-size setting does not add archive extraction/support.

## Delivery and failures

`auto_send=false` is the default: save the image and return its local/public references without posting it. Make **one explicit handoff**: present the saved result with an existing file/media tool or image-preview URL, or use the requested `image_output` handling. A post-request is explicit; do not infer delivery merely from saving.

`auto_send=true` posts once. `__IMAGE_SENT__` means it was already delivered; do not resend it. If save-only persistence fails, the tool does not silently upload instead. Generation failures, ambiguous responses and delivery failures do not trigger an automatic second generation request.

Submitted prompts, existing image sidecars, request-log correlation and media concurrency handling are retained. Website public URL settings do not redefine the separate image archive URL mapping. Publisher behavior is unchanged.

## GPT Image 2.6 (parked)

Root, 5 November 2026: the code is ready, the live default stays on GPT Image 2.5, and 2.6 is not yet on the local proxy. No 2.6 request has run. The activation steps are in [TODO.md](../TODO.md).

`IMAGE_GEN_FEATURES` is a JSON object. It maps an exact model ID in `IMAGE_GEN_MODELS` to a list of features: `gif`, `svg` and `markup`. Only the entry of `IMAGE_GEN_MODEL` is used. Without an entry, the tool schema and the request body do not change. An invalid value disables image generation, and `IMAGE_GEN_CONFIG_ERROR` names the setting.

```dotenv
IMAGE_GEN_FEATURES='{"provider/gpt-image-2.6-sunburst":["gif","svg","markup"]}'
```

| Feature | Tool arguments | Request |
|---|---|---|
| `gif` | `output_format="gif"`, `frame_count`, `frame_duration_ms` | `POST /images/generations` |
| `svg` | `output_format="svg"` | `POST /images/generations` |
| `markup` | `markup` (path, URL or data URI of a PNG) with an input image | `POST /images/edits`, field `markup: {"image_url": <data URI>}` |

- The model declares the format with the argument. No code reads the prompt to choose a format.
- A feature argument that is not enabled is refused before HTTP with the model name and the setting. Frame arguments without `output_format="gif"` are refused too.
- The API checks the ranges. The code does not clamp or change a value.
- When the bytes returned are not the format that was asked for, the tool returns an error with both formats and does not save the result. The request is not retried.
- `IMAGE_GEN_EXTRA_BODY` stays the operator's channel for `complexity` (`low`, `medium`, `high`; the API default is `high`) and `size`. These apply to every request, and the model cannot change them. Do not put an `output_format` there: a different tool argument then stops with the conflict error. Do not put frame fields there: they are for GIF requests only.
- An SVG is saved under `_images` as `.svg`, with no public URL. `scripts/publisher/scan.py` does not mirror `.svg`, and a change to that list is root's decision. Discord shows an `.svg` as a file, not as an image. `see_image` renders it to PNG. It does not render an SVG with a DOCTYPE and returns an error.

### What OpenAI documents

Read on 5 November 2026 from the [image generation guide](https://developers.openai.com/api/docs/guides/image-generation), the [Images API reference](https://developers.openai.com/api/reference/resources/images/methods/generate) and the model cards ([Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.6-sunburst), [Flare](https://developers.openai.com/api/docs/models/gpt-image-2.6-flare)).

- Models: `gpt-image-2.6-sunburst` (detailed work) and `gpt-image-2.6-flare` (fast iteration). The model cards list `v1/images/generations` and `v1/images/edits` as supported, and Chat Completions and Responses as not supported.
- Price per 1M tokens, from the model cards: text input $5, image input $8, image output $30. For SVG, the price also includes the tokens of an authoring model.
- SVG: `n` must be 1. There is no streaming, partial images, `output_compression` or `prompt_rewriter`. The edit endpoint does not make an SVG and does not accept one as input. The document is static, with no scripts, external resources or embedded raster images. The API makes a reference image first.
- The reference also lists an optional `svg` request object (`model`, `reasoning`). It needs access to SVG model selection, and the request omits it otherwise. The tool does not send it.
- GIF: `frame_count` default 9, `frame_duration_ms` default 200 and minimum 20, rounded to 10 ms. `size` is the size of each frame, `auto` or `WIDTHxHEIGHT` in multiples of 16. Frames, size and `n` must fit the pixel budget of the request. There is no streaming, partial images, custom `output_compression` or `prompt_rewriter`.
- Markup: a transparent PNG with the same width and height as the first input image, at most 16,777,216 pixels and 50 MB. Do not combine it with `mask` or `prompt_rewriter`.

The OpenAI pages do not agree on these points. Test each one when the model is available.

| Point | Guide | API reference |
|---|---|---|
| `frame_count` range | 2 to 64 | 2 to 16 |
| `frame_duration_ms` maximum | 2000 | caps the encoded delay at 655,350 |
| GIF on the edit endpoint | not supported | listed in `output_format` |
| `quality` `xhigh` and `max` on 2.6 | listed | only for 2.5 |
| What controls the SVG reference image | `quality` | `complexity` |

Not measured: GIF cost, GIF duration against `IMAGE_GEN_TIMEOUT`, and whether the local proxy passes these fields.

When `image` is omitted, message attachments become input images and the request goes to the edit endpoint. A GIF or SVG request must pass `image=""`. The API, not the code, refuses a GIF or SVG edit, because the two OpenAI pages disagree on GIF.
