FROM docker:26.1.4-cli@sha256:f13cbf1ea352bdbdc825a9233fc56716bdf818e4f608f63280a1aa0b3dc1f2f7 AS docker-cli
FROM python:3.14.4-slim-trixie AS app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg espeak-ng libopus0 libsodium23 \
    nodejs chromium stockfish fonts-dejavu-core acl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY docker/requirements.lock /opt/maxwell/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps -r /opt/maxwell/requirements.lock

WORKDIR /app
COPY autonomy.py autonomy_social.py bot.py bot_tools.py captcha_solver.py \
    channel_watch.py chess_game.py concurrency_safety.py config.py context_budget.py \
    control_defaults.py discord_vc_compat.py docker_runtime.py doctor.py \
    email_inbox.py error_reporting.py guild_onboarding.py inbox.py jobs.py knowledge_graph.py \
    message_pipeline.py operator_commands.py plugin_manager.py prompt_storage.py providers.py provider_telemetry.py \
    rag_memory.py rag_maintenance.py rem.py rem_defaults.json response_guard.py response_observability.py site_backend.py \
    site_server.py site_test.py tool_progress.py tool_registry.py tool_schemas.py \
    tools.py utils.py voice_live.py watch_policy.py x_client.py ./
COPY api/__init__.py api/api_server.py api/auth.py api/config.py api/state.py api/storage.py ./api/
COPY plugins/checkers/__init__.py plugins/checkers/checkers_game.py plugins/checkers/plugin.json plugins/checkers/tools.py ./plugins/checkers/
COPY web/index.html ./web/index.html
COPY web/admin/index.html ./web/admin/index.html
COPY docker/Dockerfile ./docker/Dockerfile
COPY docker/site-runtime/ ./docker/site-runtime/
COPY assets/tokenizers/ ./assets/tokenizers/
COPY docker/check_embeddings.py /opt/maxwell/check_embeddings.py
RUN mkdir -p /app/temp /state/data /state/sites /state/shell /config/prompts

ARG MAXWELL_BUILD_COMMIT=unknown
ARG MAXWELL_BUILD_BRANCH=unknown
ARG MAXWELL_BUILD_DATE=unknown
ARG MAXWELL_BUILD_SUBJECT=unknown
ARG MAXWELL_BUILD_DIRTY=unknown
ENV MAXWELL_BUILD_COMMIT=${MAXWELL_BUILD_COMMIT} \
    MAXWELL_BUILD_BRANCH=${MAXWELL_BUILD_BRANCH} \
    MAXWELL_BUILD_DATE=${MAXWELL_BUILD_DATE} \
    MAXWELL_BUILD_SUBJECT=${MAXWELL_BUILD_SUBJECT} \
    MAXWELL_BUILD_DIRTY=${MAXWELL_BUILD_DIRTY}
LABEL org.opencontainers.image.revision=${MAXWELL_BUILD_COMMIT}

USER 0:0
CMD ["python", "bot.py"]

FROM caddy:2.10.2-alpine AS web
RUN setcap -r /usr/bin/caddy
COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY web/index.html /srv/web/index.html
COPY web/admin/index.html /srv/web/admin/index.html
