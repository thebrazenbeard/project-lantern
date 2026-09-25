> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# Project Lantern

Project Lantern is a Python qualification and orchestration workspace that lives alongside the Build Team 2.0 implementation.

The repository contains executable source under `src/lantern` and `src/build_team`, tests, project snapshots under `projects/`, and a `lantern` command-line entry point declared in `pyproject.toml`.

## Current status

`main` is the canonical repository branch for the source currently visible here. Repository source does not by itself prove deployment, installation, provider activation, or runtime use.

## Scope

- preserve Lantern qualification/orchestration source;
- keep Build Team support code and Lantern code separable but compatible;
- retain tests and project evidence needed to reproduce qualification work;
- keep repository state distinct from any live provider or deployed runtime.

## Development

The package targets Python 3.11+ and exposes two command-line entry points:

- `build-team` → `build_team.cli:app`
- `lantern` → `lantern.cli:main`

Use the tests and repository contracts as the evidence surface for source-level behavior.
