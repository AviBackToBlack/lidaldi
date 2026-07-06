# Test environment = pinned official Playwright image (Node LTS +
# Chromium/Firefox/WebKit with deps; Ubuntu noble -> python3.12) + make.
FROM mcr.microsoft.com/playwright:v1.61.1-noble
RUN apt-get update && apt-get install -y --no-install-recommends make python3-venv \
    && rm -rf /var/lib/apt/lists/*
# k6 for the load tier (T13): pinned version, checksum-verified. The same
# script installs k6 in CI so local == CI. Build context is the repo root
# (see docker-compose.yml).
COPY tests/load/install-k6.sh /tmp/install-k6.sh
RUN bash /tmp/install-k6.sh && rm /tmp/install-k6.sh
