# Test environment = pinned official Playwright image (Node LTS +
# Chromium/Firefox/WebKit with deps) + pyenv Python 3.12.13 + make.
FROM mcr.microsoft.com/playwright:v1.62.0-noble
ENV PYENV_ROOT=/opt/pyenv
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
ARG PYENV_REF=933d0aaf1d1190a641c3ddce484e72b1a993473d
ARG PYENV_VIRTUALENV_REF=eda64556af9b2992386deeb75dad2130899fc4c9
ARG PYENV_PYTHON_VERSION=3.12.13
RUN apt-get update && apt-get install -y --no-install-recommends \
        make git ca-certificates curl build-essential libssl-dev zlib1g-dev \
        libbz2-dev libreadline-dev libsqlite3-dev libncursesw5-dev xz-utils \
        tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
    && git init "$PYENV_ROOT" \
    && git -C "$PYENV_ROOT" remote add origin https://github.com/pyenv/pyenv.git \
    && git -C "$PYENV_ROOT" fetch --depth 1 origin "$PYENV_REF" \
    && git -C "$PYENV_ROOT" checkout --detach FETCH_HEAD \
    && mkdir -p "$PYENV_ROOT/plugins" \
    && git init "$PYENV_ROOT/plugins/pyenv-virtualenv" \
    && git -C "$PYENV_ROOT/plugins/pyenv-virtualenv" remote add origin https://github.com/pyenv/pyenv-virtualenv.git \
    && git -C "$PYENV_ROOT/plugins/pyenv-virtualenv" fetch --depth 1 origin "$PYENV_VIRTUALENV_REF" \
    && git -C "$PYENV_ROOT/plugins/pyenv-virtualenv" checkout --detach FETCH_HEAD \
    && pyenv install "$PYENV_PYTHON_VERSION" \
    && pyenv virtualenv "$PYENV_PYTHON_VERSION" lidaldi \
    && rm -rf /var/lib/apt/lists/*
# k6 for the load tier (T13): pinned version, checksum-verified. The same
# script installs k6 in CI so local == CI. Build context is the repo root
# (see docker-compose.yml).
COPY tests/load/install-k6.sh /tmp/install-k6.sh
RUN bash /tmp/install-k6.sh && rm /tmp/install-k6.sh
