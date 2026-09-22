# Lantern Public API V1

Status: SOURCE CONTRACT / NO DOMAIN-AUTHORITY TRANSFER

The stable package import is `lantern`.

The narrow public Python surface exported by `src/lantern/__init__.py` is:

- `LanternStore`
- `OperationResult`
- `RecordEnvelope`
- `build_record`
- `parse_record`

The stable command-line entry point is `lantern`.

Project Lantern provides generic evidence custody, canonical record construction, lineage, source capture, links, assessments, decisions, and import/export mechanics. It does not decide whether a consumer's proposition is true, whether evidence is current for that consumer, whether an action is authorized, whether a scientific hypothesis passes, or whether a runtime effect should occur.

Compatibility rule: changes that remove or semantically broaden this public surface require an explicit successor contract and consumer review.
