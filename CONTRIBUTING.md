# Contributing

Thanks for contributing to Lidaldi.

## Development setup

Use the repository devcontainer/Makefile workflow where practical so local development matches CI. Before opening a pull request, run:

```bash
make test
```

If your change affects frontend/end-to-end behavior, run the relevant frontend and Playwright checks as well.

## Pull requests

- Keep changes focused and explain user-visible/data-contract effects in the PR body.
- Add or update tests for bug fixes and behavior changes.
- Preserve scraper/data normalization contracts unless an intentional migration is documented.
- Keep the Vite, `@sveltejs/vite-plugin-svelte`, and Vitest toolchain compatible; these dependencies are intentionally updated together.
- Do not commit credentials, cookies, real `.env` values, private deployment data, or generated secrets.
- Required CI and security checks must pass, and review conversations must be resolved before merge.

## Security issues

Do not report suspected vulnerabilities in public issues. Follow `SECURITY.md` and use GitHub private vulnerability reporting when available.
