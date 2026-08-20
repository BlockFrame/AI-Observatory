# Documentation

Wiredframe Radar keeps the repository root focused on executable entry points, platform configuration, and files automatically discovered by GitHub or coding agents. Public project documentation lives here.

## Guides

| Document | Purpose |
|---|---|
| [Project overview](project-overview.md) | Product goals, differentiators, inputs, and technology |
| [Getting started](getting-started.md) | Installation, local execution, recovery, and validation |
| [Architecture](architecture.md) | Pipeline topology, processing sequence, contracts, and failure boundaries |
| [Source inventory](sources.md) | Active News, Research, Social, and GitHub collection paths |
| [Deployment](deployment.md) | GitHub Actions, Vercel, diagnostics, and rollback |
| [Roadmap](roadmap.md) | Open strategic work and product backlog |
| [AI development lifecycle](ai-development-lifecycle.md) | AIDLC controls, review model, and operational workflow |
| [Project governance](governance.md) | Roles, decisions, review policy, releases, and automation exceptions |

## Naming convention

Documentation uses lowercase kebab-case filenames. Conventional discovery files remain uppercase where required or expected: `README.md`, `AGENTS.md`, `CLAUDE.md`, and `LICENSE`.

Configuration under `config/` retains the naming expected by the application. Generated reports under `web/data/` are artifacts rather than project documentation.

Optional dependency groups live under `requirements/`; the primary runtime dependencies remain in the conventional root `requirements.txt`.
