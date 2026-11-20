> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# Project Lantern

Project Lantern is a durable evidence-custody and provenance package. It provides canonical record construction, source custody, lineage, assessments, decisions, links, and portable import/export mechanics without turning stored evidence into domain authority.

The executable package source is under `src/lantern`, with tests under `tests/lantern`, project snapshots under `projects/`, and the `lantern` command-line entry point declared in `pyproject.toml`. The repository does not contain a `src/build_team` package.

## Current status

`main` is the canonical repository branch for the source currently visible here. Repository source does not by itself prove deployment, installation, provider activation, or runtime use.

## Lantern currentness

WoWSQL is retired from Lantern currentness. The current BT2 source contains a provider-neutral PostgreSQL / SQL Connectome V4 replacement contract, but source presence is not runtime installation or qualification. Until a replacement PostgreSQL runtime is reconstructed, qualified, connected through the governed V4 interface, and installed as the active Project contract:

`LANTERN_CURRENTNESS = UNKNOWN`

Do not fall back to WoWSQL, Supabase, Git source, project prose, benchmark fixtures, chat history, model memory, or inference as current Lantern runtime state. The machine-readable current binding status is `projects/lantern/CURRENTNESS_STATUS_V3.json`: active backend is null, replacement backend is `NOT_ESTABLISHED`, and V4 remains source-candidate material only. Historical rationale remains in `projects/lantern/CURRENTNESS_STATUS_V2.md`.

## Scope

- preserve Lantern evidence-custody and qualification source;
- keep its public Python and CLI surfaces narrow and explicit;
- retain tests and project evidence needed to reproduce qualification work;
- keep repository state distinct from any live provider or deployed runtime.

## Development

The package targets Python 3.11+ and exposes one command-line entry point:

- `lantern` → `lantern.cli:main`

Its stable Python surface is documented in `docs/LANTERN_PUBLIC_API_V1.md`. Use the tests and repository contracts as the evidence surface for source-level behavior.

## Editor startup containment — tracked source (2026-11-20)

The tracked `main` source formerly contained a concealed VS Code `folderOpen` task invoking obfuscated `.vscode/ini` through Node. The task list is now empty, `task.allowAutomaticTasks` is explicitly `"off"`, and the obfuscated file is removed from this source tree. Historical Git source remains for investigation.

**Limits:** This is source-only containment, not proof that older checkouts, editor extensions, user/global settings, local credentials, or any previous host execution are safe. Do not execute historical suspect assets.
