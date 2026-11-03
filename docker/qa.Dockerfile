# QA image: the app image plus the pinned test tools. Build: scripts/build_qa_image.sh <app-tag>
ARG APP_IMAGE
FROM ${APP_IMAGE}
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends git rsync openssh-client >/dev/null \
    && rm -rf /var/lib/apt/lists/*
COPY qa-requirements.lock /tmp/qa-requirements.lock
RUN python -m pip install --no-cache-dir --no-deps -r /tmp/qa-requirements.lock
