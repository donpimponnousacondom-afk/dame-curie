#!/bin/bash

rev=$(git rev-parse HEAD)
image="maxwell-app:${rev:0:7}"

git archive "$rev" |
sudo -n runuser -u maxwell-curie -- \
  env DOCKER_HOST=unix:///run/user/1003/docker.sock \
  docker build --target app -f docker/app.Dockerfile \
    --build-arg MAXWELL_BUILD_COMMIT="$rev" \
    --build-arg MAXWELL_BUILD_BRANCH="$(git branch --show-current)" \
    --build-arg MAXWELL_BUILD_DATE="$(git show -s --format=%cI "$rev")" \
    --build-arg MAXWELL_BUILD_SUBJECT="$(git show -s --format=%s "$rev")" \
    --build-arg MAXWELL_BUILD_DIRTY=false \
    -t "$image" -

git archive "$rev" | sudo -n tar -x -C /opt/maxwell

sudo -n runuser -u maxwell-curie -- \
  sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$image|" /srv/maxwell/curie/deploy.env

sudo -n /usr/local/bin/python3.14 /opt/maxwell/scripts/instance.py curie up

sudo -n runuser -u maxwell-curie -- \
  env DOCKER_HOST=unix:///run/user/1003/docker.sock \
  docker inspect maxwell-curie-bot-1 \
    --format 'Image: {{.Config.Image}} | Image ID: {{.Image}} | Started: {{.State.StartedAt}}'
