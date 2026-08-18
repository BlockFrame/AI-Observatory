# Contributing

Thanks for helping improve Wiredframe Radar. Changes should preserve evidence grounding, quota safety, and last-good publishing behavior.

## Before opening a pull request

1. Keep provider credentials and raw production responses out of the repository.
2. Do not run paid providers or GetXAPI unless the test explicitly requires it and you control the account.
3. Add mocked regression coverage for new behavior and failure paths.
4. Update `docs/sources.md` when changing collection inputs.
5. Update `docs/architecture.md` when changing pipeline boundaries or data contracts.

Run the local checks:

```bash
python -m unittest discover -s tests -p '*_test.py'
npm run check
npm run build
```

Generated reports must pass the validator before publication:

```bash
python scripts/validate_report.py --web-dir ./web --date YYYY-MM-DD
```

See [AGENTS.md](../AGENTS.md) for repository-specific safety and reliability requirements.
