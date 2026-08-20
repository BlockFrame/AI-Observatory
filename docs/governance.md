# Project governance

Wiredframe Radar is an open-source project maintained in public. Decisions favor evidence grounding, operational reliability, security, cost awareness, and a clear contributor experience.

## Roles

| Role | Responsibilities | How it is earned |
|---|---|---|
| Contributor | Opens issues, proposes changes, tests behavior, and participates in review. | Any community participant following the Code of Conduct. |
| Reviewer | Reviews changes in a demonstrated area of expertise and helps triage issues. | Repeated high-quality contributions and sound technical judgment. |
| Maintainer | Merges pull requests, manages releases and security, and makes final project decisions. | Sustained contributions, trusted review work, and explicit invitation by existing maintainers. |

Roles are based on demonstrated contribution, not employment or use of AI tooling. Maintainer access is granted with least privilege and reviewed when responsibilities change.

## Contribution and release model

The repository follows trunk-based development:

1. Start from an issue when the change is material.
2. Work in a fork or short-lived branch named `type/concise-description`, such as `fix/rss-timeout`.
3. Open a pull request against `main` early enough for review and a Vercel Preview.
4. Resolve required checks, review comments, and conversations.
5. A maintainer squash-merges the pull request after approval.

There is no permanent `dev` branch. `main` is the single integration branch and must remain releasable. Production deploys are derived from `main`; pull requests receive isolated, non-indexed Preview deployments.

## Decision making

Routine changes use lazy consensus in the pull request: maintainers consider technical evidence, tests, user impact, security, provider cost, and maintainability. Substantial architecture, source-policy, data-contract, or governance changes should begin as an issue or discussion and document the selected option and alternatives.

Maintainers seek consensus. If consensus cannot be reached, the lead maintainer makes the final decision and records the rationale publicly. Security incidents and embargoed vulnerabilities are handled privately until coordinated disclosure is safe.

## Review policy

Human-authored code and configuration changes require:

- a pull request targeting `main`;
- all required automated checks passing on the latest commit;
- one approving review, including CODEOWNERS review where applicable;
- all review conversations resolved;
- disclosure of material AI assistance and human verification.

High-risk areas include provider routing and billing, credentials, workflows, publishing gates, evidence contracts, and generated-data integrity. Maintainers may request additional reviewers or validation for these areas.

The repository administrator retains an emergency bypass for incident recovery. Its use must be exceptional, documented in an issue or follow-up pull request, and followed by the checks that could not run beforehand.

## Automated publishing exception

The scheduled GitHub Actions pipeline may write validated generated reports directly to `main`. This is a narrow automation exception, not a general code-change path. The workflow:

- runs regression tests before paid calls;
- validates generated output before commit;
- writes only expected report and discovery artifacts;
- authenticates with a repository-scoped writable deploy key as the allowed ruleset bypass;
- leaves human-authored source and configuration changes subject to pull-request review.

## Community and security

Participation is governed by the [Code of Conduct](../.github/CODE_OF_CONDUCT.md). Security vulnerabilities must follow the [private reporting policy](../.github/SECURITY.md). General defects, proposals, and operational incidents belong in Issues; design questions and broader proposals may use Discussions.

Governance changes follow the same pull-request process as code changes.
