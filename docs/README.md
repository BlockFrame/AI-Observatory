# Documentation

This directory is the canonical, versioned documentation for R[AI]DAR. The [project README](../README.md) is the public landing page; the [GitHub Wiki](https://github.com/BlockFrame/wiredframe-radar/wiki) provides a shorter, task-oriented navigation layer and links back here for implementation detail.

## Start here

| Document | Purpose |
|---|---|
| [Project overview](project-overview.md) | Product goals, differentiators, inputs, and technology |
| [Getting started](getting-started.md) | Installation, local execution, recovery, and validation |

## Understand the system

| Document | Purpose |
|---|---|
| [Architecture](architecture.md) | Pipeline topology, processing sequence, contracts, and failure boundaries |
| [Source handbook](sources.md) | Complete inventory, category boundaries, freshness rules, telemetry, and contribution workflow |

## Operate R[AI]DAR

| Document | Purpose |
|---|---|
| [Deployment](deployment.md) | GitHub Actions, Vercel, diagnostics, and rollback |
| [Operations runbook](operations.md) | Daily checks, reruns, incidents, paid-call safety, and recovery |

## Contribute and govern

| Document | Purpose |
|---|---|
| [AI development lifecycle](ai-development-lifecycle.md) | AIDLC controls, review model, and operational workflow |
| [Project governance](governance.md) | Roles, decisions, review policy, releases, and automation exceptions |
| [Contribution guide](../.github/CONTRIBUTING.md) | Setup, branch model, checks, and pull-request expectations |
| [Security policy](../.github/SECURITY.md) | Supported version and private vulnerability reporting |
| [Roadmap](roadmap.md) | Open strategic work and product backlog |

## Documentation ownership

- Runtime behavior belongs in this directory and must change in the same pull request as the code or configuration it describes.
- Source counts and model routes must be verified against `config/`, not copied from an old report or Wiki page.
- The Wiki should summarize workflows and point to canonical pages; it should not become an independent configuration reference.
- Security reporting remains canonical in `.github/SECURITY.md`, while contributor policy remains canonical in `.github/CONTRIBUTING.md` and `docs/governance.md`.

## Naming convention

Documentation uses lowercase kebab-case filenames. Conventional discovery files remain uppercase where required or expected: `README.md`, `AGENTS.md`, `CLAUDE.md`, and `LICENSE`.

Configuration under `config/` retains the naming expected by the application. Generated reports under `web/data/` are artifacts rather than project documentation.

Optional dependency groups live under `requirements/`; the primary runtime dependencies remain in the conventional root `requirements.txt`.
