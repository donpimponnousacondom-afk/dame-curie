#!/bin/bash

rev=$(git rev-parse HEAD)
image="dame-curie-app:${rev:0:7}"
uid=$(id -u dame-curie)

git archive "$rev" |
sudo -n runuser -u dame-curie -- \
  env DOCKER_HOST=unix:///run/user/"$uid"/docker.sock \
  docker build --target app -f docker/app.Dockerfile \
    --build-arg DAME_CURIE_BUILD_COMMIT="$rev" \
    --build-arg DAME_CURIE_BUILD_BRANCH="$(git branch --show-current)" \
    --build-arg DAME_CURIE_BUILD_DATE="$(git show -s --format=%cI "$rev")" \
    --build-arg DAME_CURIE_BUILD_SUBJECT="$(git show -s --format=%s "$rev")" \
    --build-arg DAME_CURIE_BUILD_DIRTY=false \
    -t "$image" -

git archive "$rev" | sudo -n tar -x -C /opt/dame-curie

sudo -n runuser -u dame-curie -- \
  sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$image|" /srv/dame-curie/deploy.env

sudo -n runuser -u dame-curie -- \
  /opt/dame-curie/.venv/bin/python /opt/dame-curie/scripts/instance.py dame-curie up

sudo -n runuser -u dame-curie -- \
  env DOCKER_HOST=unix:///run/user/"$uid"/docker.sock \
  docker inspect dame-curie-bot-1 \
    --format 'Image: {{.Config.Image}} | Image ID: {{.Image}} | Started: {{.State.StartedAt}}'
