FROM python:3.14.4-slim-trixie AS app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg espeak-ng libopus0 libsodium23 \
    nodejs chromium stockfish fonts-dejavu-core acl \
    bind9-dnsutils bind9-host bzip2 g++ git iputils-ping jq make nano \
    net-tools netcat-traditional patch procps tesseract-ocr \
    tesseract-ocr-eng tesseract-ocr-osd vim wget xz-utils \
    && rm -rf /var/lib/apt/lists/*
COPY docker/requirements.lock /opt/dame-curie/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps -r /opt/dame-curie/requirements.lock
COPY docker/shell-requirements.lock /opt/dame-curie/shell-requirements.lock
RUN python -m pip wheel --no-cache-dir --no-deps \
    --wheel-dir /opt/dame-curie/shell-wheelhouse -r /opt/dame-curie/shell-requirements.lock

WORKDIR /app
COPY autonomy.py autonomy_social.py bot.py bot_tools.py captcha_solver.py \
    channel_watch.py chess_game.py concurrency_safety.py config.py context_budget.py \
    control_defaults.py dirac_runtime.py discord_vc_compat.py docker_runtime.py doctor.py \
    error_reporting.py guild_onboarding.py image_media.py inbox.py job_routing.py jobs.py knowledge_graph.py \
    message_pipeline.py operator_commands.py plugin_manager.py prompt_storage.py providers.py provider_telemetry.py \
    provider_settings.py provider_reload.py \
    rag_memory.py rag_maintenance.py rem.py rem_defaults.json response_guard.py response_observability.py smoke_protocol.py \
    tool_policy.py tool_progress.py tool_prompts.py tool_registry.py tool_schemas.py \
    tools.py turn_budget.py utils.py voice_live.py watch_policy.py ./
COPY plugins/checkers/__init__.py plugins/checkers/checkers_game.py plugins/checkers/plugin.json plugins/checkers/tools.py ./plugins/checkers/
COPY assets/tokenizers/ ./assets/tokenizers/
COPY docker/check_embeddings.py /opt/dame-curie/check_embeddings.py
RUN mkdir -p /app/temp /state/data /state/sites /state/shell /config/prompts \
    && ln -sT /state/shell /home/dame-curie \
    && ln -sT /state/shell /home/maxwell
ENV HOME=/home/dame-curie

ARG DAME_CURIE_BUILD_COMMIT=unknown
ARG DAME_CURIE_BUILD_BRANCH=unknown
ARG DAME_CURIE_BUILD_DATE=unknown
ARG DAME_CURIE_BUILD_SUBJECT=unknown
ARG DAME_CURIE_BUILD_DIRTY=unknown
RUN python -c 'import json, os, re; from datetime import datetime; from pathlib import Path; \
    fields = ("commit", "branch", "date", "subject"); \
    manifest = {name: os.environ["DAME_CURIE_BUILD_" + name.upper()] for name in fields}; \
    assert re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", manifest["commit"]), "Full build commit required"; \
    assert all(manifest[name].strip() for name in fields), "Complete build metadata required"; \
    assert datetime.fromisoformat(manifest["date"]).tzinfo is not None, "Timezone-aware commit date required"; \
    manifest["dirty"] = {"true": True, "false": False}[os.environ["DAME_CURIE_BUILD_DIRTY"]]; \
    Path("/app/build_provenance.json").write_text(json.dumps(manifest), encoding="utf-8")'
LABEL org.opencontainers.image.revision=${DAME_CURIE_BUILD_COMMIT}

USER 0:0
CMD ["python", "bot.py"]
