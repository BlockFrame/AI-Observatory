# Security policy

## Supported version

The `main` branch and the production deployment at [radar.wiredframe.xyz](https://radar.wiredframe.xyz) are actively maintained. Historical report data is immutable and is not a separately supported software version.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability, exposed credential, or data-security concern.

Use [private vulnerability reporting](https://github.com/BlockFrame/wiredframe-radar/security/advisories/new) to send:

- a concise description and impact assessment;
- steps to reproduce or a proof of concept;
- affected paths, commits, or deployment URLs;
- suggested remediation, if available.

We will acknowledge the report, assess severity, and coordinate remediation privately before any disclosure. Do not include live API keys, access tokens, or personal data in the report.

## Security boundaries

The pipeline uses third-party content and paid providers. Never commit credentials, raw production prompts, or provider responses containing sensitive information. Use mocked tests for normal development and keep the publish validator enabled.
