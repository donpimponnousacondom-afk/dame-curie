# Offline telemetry tokenizer

`cl100k_base.tiktoken` is OpenAI's CL100K mergeable-rank vocabulary, used with the encoding definition from pinned `tiktoken==0.14.0`. It provides a consistent local estimate when a provider omits token counts; it is not a claim that every model uses CL100K.

- Source: https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
- SHA-256: `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`
- Encoding definition: `tiktoken_ext/openai_public.py::cl100k_base` in the pinned `tiktoken==0.14.0` distribution.
- License: see `LICENSE` alongside the vocabulary.

The runtime loads this checked local file, not a tokenizer downloaded on the first model request. Provider-reported output counts, including their reasoning component, take precedence. Local estimates and unavailable hidden reasoning are identified in telemetry rather than presented as official model counts.
