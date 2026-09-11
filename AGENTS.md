# AGENTS.md

Repository-wide instructions for coding agents and automation.

## Project intent

Lidaldi aggregates and presents Irish ALDI/LIDL offers. Preserve scraper correctness, normalized offer data, frontend/backend compatibility, and reproducible local/CI behavior.

## Existing project guidance

`CLAUDE.md` contains substantial historical/project-specific guidance. Treat it as an additional source while this repository is being consolidated toward agent-agnostic instructions; do not silently discard constraints from it.

## Development

- Use the repository Makefile/devcontainer workflow where practical so local behavior matches CI.
- Run `make test` before proposing behavioral changes.
- Keep frontend, backend, scraper, and end-to-end dependency compatibility in mind.
- The Vite/Svelte/Vitest toolchain is intentionally updated atomically; do not split those dependency updates.
- Add regression tests for bug fixes and data-processing changes.

## Safety and supply chain

- Never commit real `.env` values, credentials, tokens, cookies, or private deployment data.
- Keep GitHub Actions dependencies pinned to full commit SHAs with readable version comments.
- Do not weaken CI, Snyk, dependency review, CodeQL, secret scanning, or repository governance merely to make a change pass.

## Documentation

Update README and relevant design/runbook documentation when user-visible behavior, setup, deployment assumptions, data formats, or architectural constraints change.
