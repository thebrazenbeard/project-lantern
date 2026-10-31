> **License:** Source-visible, not open source. Original material is proprietary. Commercial use, redistribution, hosted-service use, and commercial derivative products require written permission. See [LICENSE](LICENSE) and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md). Separately identified third-party components retain their own licenses.

# Project Lantern — Evidence custody and provenance

Project Lantern is a reusable **Python library and command-line tool for local evidence records**. It records sources, claims, assessments, decisions, links, and their lineage in a canonical, content-addressed form. Its purpose is to preserve *what was recorded, how it was attributed, and how records relate*—not to decide whether a claim is true or whether its author is authorized.

The package is `project-lantern` (Python 3.11+), with the public import `lantern` and CLI command `lantern`. It has no declared mandatory third-party runtime dependencies. The source and tests live in [`src/lantern/`](src/lantern/) and [`tests/lantern/`](tests/lantern/).

## What you can build with it

- **Research or audit trails:** capture a source reference or content, then associate a claim with later assessments, revisions, and supporting or opposing links.
- **Reproducible evidence packages:** construct canonical record envelopes with hashes, attribution fields, and lineage relationships.
- **Local review workflows:** query record counts, review status, and decision traces without treating an assessment as an external authorization grant.
- **Explicit interchange:** export and import bounded evidence bundles where the implementation can satisfy its filesystem and atomic-publication requirements.
- **Benchmark evidence:** score a frozen set of measurements against a specified benchmark contract and freeze receipt.

The stable Python surface is deliberately narrow: `LanternStore`, `OperationResult`, `RecordEnvelope`, `build_record`, and `parse_record`. See the [public API contract](docs/LANTERN_PUBLIC_API_V1.md) for the compatibility boundary.

## Quick start

From a checkout, in a Python 3.11+ environment:

```sh
python -m pip install -e .
lantern --project ./example-evidence init --name "Sample Research" --actor-id analyst
lantern --project ./example-evidence claim add \
  --actor-id analyst \
  --claim-key example-001 \
  --text "The specimen requires follow-up review." \
  --epistemic-class hypothesis \
  --attributable-to analyst
lantern --project ./example-evidence status
```

Each command emits a structured JSON response. The example initializes a **new local project** and records a *claim*, not an established conclusion. Source observation, assessment, link, decision, export/import, and benchmark commands are discoverable with `lantern --help` and their respective subcommand help.

For applications, import the documented public names from `lantern`; treat the returned operation receipts as **local data-integrity evidence**, not as externally verified identity, permission, or consent.

## Custody and publication boundaries

- The store tracks source metadata, optional content custody, canonical hashes, and explicit record relationships. A stored URL or attributed actor ID is caller-provided evidence, **not proof that a provider or person was authenticated**.
- The repository's interchange implementation uses bounded staging and atomic no-replace publication. On Linux, directory publication currently requires the **ext4** filesystem profile; unknown or unsupported filesystems (including overlay in typical containers) are rejected rather than silently weakening the atomicity guarantee. See [`src/lantern/_store_portability.py`](src/lantern/_store_portability.py).
- The package does **not** make a domain claim true, establish external source currentness, enforce host-owned immutable authority, grant permission for an effect, or prove deployment in another system.
- Historical project integration notes are **not** an active backend binding. The [machine-readable currentness record](projects/lantern/CURRENTNESS_STATUS_V3.json) marks the replacement backend as not established and the active backend as null. The [historical rationale](projects/lantern/CURRENTNESS_STATUS_V2.md) remains available, but source presence must not be promoted into a live runtime claim.

## Lantern currentness

`LANTERN_CURRENTNESS = UNKNOWN` is the repository's fail-closed project-integration status. The [currentness rationale](projects/lantern/CURRENTNESS_STATUS_V2.md) and [machine-readable status](projects/lantern/CURRENTNESS_STATUS_V3.json) are source records, not a verified active backend, live host binding, or authorization grant. In particular, a successful local CLI operation does not establish current project installation or consumption by another runtime.

## Test and contribution guidance

The [CI workflow](.github/workflows/ci.yml) installs the development extras, runs pytest, compiles source, builds distributions, and smokes the public package surface. To run it locally:

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```

Tests involving export/import require a compatible local filesystem profile. A test failure on an unsupported overlay mount is a **fail-closed deployment boundary**, not evidence that the export completed. Passing tests establish bounded source behavior, not a provider attestation or real-host authorization service.

Contributors should read [CONTRIBUTING.md](CONTRIBUTING.md), [CLA.md](CLA.md), and the license before proposing changes; they must be able to make their own required rights and provenance representations.
