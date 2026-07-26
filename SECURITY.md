# Security Policy

## Supported versions

LidAldi has no release branches — `main` is the only version deployed
([lidaldi.neit.me](https://lidaldi.neit.me/)) and the only one that
receives fixes.

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.

Use GitHub's private reporting flow instead: go to the
[Security tab](https://github.com/AviBackToBlack/lidaldi/security) →
**Report a vulnerability**. This opens a private advisory visible only
to the maintainer until a fix is ready.

If that option isn't available, open an issue asking for a private
contact channel — don't include exploit details or affected data in it.

Include, where relevant: the affected component (scraper, sync server,
frontend, deploy tooling), reproduction steps, and potential impact.

We aim to acknowledge reports within a few days. Automated dependency
and code scanning (Dependabot, Snyk, CodeQL) already run continuously
against `main`; this policy is for issues those tools can't catch —
logic bugs, auth/session handling, and the sync API contract in
particular (see `docs/sync-contract.md`).
