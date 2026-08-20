# Contributing

Thanks for helping improve Wiredframe Radar. Contributions of code, source maintenance, documentation, tests, issue triage, and design feedback are welcome. By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Development model

The project uses trunk-based development. There is no permanent `dev` branch:

1. Fork the repository or create a short-lived branch from the latest `main`.
2. Use a descriptive name such as `fix/rss-timeout`, `feat/source-health`, or `docs/provider-routing`.
3. Open a pull request against `main`; every pull request receives an isolated Vercel Preview.
4. Keep the change focused, respond to review, and squash-merge after approval and required checks.

For material work, open or reference an issue first. Security vulnerabilities must be reported privately according to the [security policy](SECURITY.md).

## Local setup

Requirements are Python 3.11+, Node.js 20+, and Git. Follow the [getting-started guide](../docs/getting-started.md) to install dependencies and configure optional providers.

Do not run paid providers or GetXAPI for routine development. The unit suite mocks external calls and must not consume provider quota.

## Change requirements

Before opening a pull request:

1. Keep credentials, raw production responses, checkpoints, and local environment files out of the repository.
2. Add mocked regression coverage for changed behavior and failure paths.
3. Preserve evidence IDs, source grounding, quota safety, and last-good publishing behavior.
4. Update `docs/sources.md` when changing collection inputs.
5. Update `docs/architecture.md` when changing pipeline boundaries or data contracts.
6. Do not manually edit generated reports unless the change explicitly concerns fixtures or recovery.

Run the local checks from the repository root:

```bash
python -m unittest discover -s tests -p '*_test.py'
npm run check
npm run build
```

Generated reports must pass the validator before publication:

```bash
python scripts/validate_report.py --web-dir ./web --date YYYY-MM-DD
```

The pull request must describe the outcome, validation evidence, external-call or cost impact, and rollback considerations. Disclose material AI assistance and record what a human independently reviewed.

## Review and merge

Required checks and an approving review must apply to the latest commit. CODEOWNERS review is required for protected operational areas. Resolve all review conversations before merge.

Maintainers normally squash-merge. Do not force-push `main`, bypass checks for convenience, or use the daily publishing workflow to land source-code changes. See [project governance](../docs/governance.md) and [AGENTS.md](../AGENTS.md) for the complete operating model.
