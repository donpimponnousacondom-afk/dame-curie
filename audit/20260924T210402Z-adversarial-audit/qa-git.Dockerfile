FROM dame-curie-dirac-qa:20260922 AS git_source
RUN apt-get -o Acquire::Retries=0 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update \
    && apt-get install -y --no-install-recommends --no-upgrade \
        git=1:2.47.3-0+deb13u1 git-man=1:2.47.3-0+deb13u1 \
    && dpkg-query -W -f='${Package}=${Version}\n' git git-man \
    && rm -rf /var/lib/apt/lists/*

FROM dame-curie-dirac-qa:20260922
COPY --from=git_source /usr/bin/git /usr/bin/git
COPY --from=git_source /usr/share/git-core/templates/ /usr/share/git-core/templates/
