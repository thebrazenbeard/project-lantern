# Project Lantern

Project Lantern is a durable evidence-custody and provenance ledger.

It provides immutable/canonical record construction, source custody, claims, assessments, decisions, links, lineage, export/import, crash-safe store operations, and deterministic benchmark/fixture support.

Lantern owns custody mechanics, not domain truth. Consumers remain responsible for their own semantic validity, authority, privacy, currentness, and acceptance rules.

## Package

- Python import: `lantern`
- CLI: `lantern`
- Python: 3.11+
- public package surface: `LanternStore`, `OperationResult`, `RecordEnvelope`, `build_record`, `parse_record`

This repository does not define a global truth database or authorize downstream actions merely because evidence was recorded.
