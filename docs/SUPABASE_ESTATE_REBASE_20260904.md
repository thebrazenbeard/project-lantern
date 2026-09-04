# Project Lantern — Supabase estate rebase 2026-09-04

Status: **WORKING AUDIT / SOURCE-ONLY / NO PRODUCTION MUTATION**

This document records the observed state of the Project Lantern Supabase project before accepting Build Team Two state from Vera production. It prevents an incoming BT2 migration from treating Lantern as an empty target or silently adopting old construction artifacts as current architecture.

## Bound provider and source cut

- Project Lantern Supabase: `agvhmutlrolbaijzlbqk` (`us-west-2`, Postgres 17)
- Project Lantern source: `thebrazenbeard/project-lantern@6333d386c74ce37e644fa1e995be9f9dc3fe6394`

## Active observed Lantern data

Current meaningful application data is concentrated in `lantern_material`:

- `accepted_profile`: 1 row
- `material`: 2 rows
- `producer_grant`: 3 rows
- `admission_receipt`: 2 rows
- `schema_policy`: 1 row
- `seed_import_receipt`: 0 rows

Cumulative table statistics show actual access/activity concentrated here.

## Other hosted structures

Lantern also contains older construction-era schemas including:

- `governance`
- `r9a0_api`
- `r9a0_coordination`
- `r9a0_governance`
- `bug_ops`
- `pgmq`

Observed R9A0 coordination/governance application tables are effectively empty at this cut.

Observed Lantern `bug_ops` is empty:

- bug reports: 0
- bug events: 0
- dispatch events: 0
- operation receipts: 0
- system config: 0
- role registry: 0

PGMQ has physical queue/meta artifacts for bug dispatch and role work queues, but all observed queue/archive relations are empty. Lantern's bug-operation migration lineage predates Vera's later replay-safety/project-key/Voss-retirement changes.

Classification: **DORMANT / STALE CONSTRUCTION COPY**, not current shared bug authority and not automatically RETIRE. Reuse or retirement requires explicit ownership/dependency evidence.

### Dependency evidence for dormant construction schemas

Fresh catalog inspection found no cross-schema foreign keys involving `r9a0_*`, `governance`, `bug_ops`, or `lantern_material`.

The R9A0 coordination views/functions reference their own R9A0 schemas, and the bug-operation functions reference their own bug subsystem. `lantern_material.runtime_visible_v1` references only Lantern material tables. This is favorable for future separation/retirement because the database does not currently encode FK-level coupling between these domains.

Current `project-lantern@main` indexed source search returned no reference to `r9a0_api` or `bug_ops`. That strengthens DORMANT/RETIRE-CANDIDATE classification for the empty construction-era surfaces, but it does **not** prove no external/unindexed caller exists. Production deletion still requires caller/currentness proof and separate authority.

## Other provider surfaces

At the observed cut:

- Auth users: 0
- Storage buckets: 0
- Storage objects: 0
- Edge Functions: 0
- Realtime publications: none observed
- Vault application secret metadata: none observed
- Cron/Webhook/pg_net application automation: none observed

These are observations, not commitments that the surfaces must remain unused.

## Source reproducibility defect

The current Project Lantern repository tree does not visibly contain a normal Supabase migration directory representing the live `lantern_material`, R9A0-era, or bug-operation schema history.

Therefore hosted database state currently carries migration/configuration history that the nominal project source tree cannot fully recreate by itself. Before expanding Lantern with BT2, establish a versioned database source-of-truth policy and reconstruct the admitted live baseline rather than compounding Dashboard/remote-only configuration drift.

## Incoming BT2 boundary

Patrick has stated that Build Team Two material may move from Vera production Supabase into Project Lantern Supabase.

That does **not** mean:

- BT2 should be folded into `lantern_material` tables;
- old Lantern bug queues should become BT2 infrastructure merely because they already exist;
- Vera bug operations, Radar, Semantic Atlas, Redworm, Brigit state, Vera memory/continuity, or Vera Storage should move with it;
- a permanent FDW/cross-project database join is an acceptable substitute for project separation.

A deliberate `build_team_2` namespace is available at this cut and should preserve BT2's own service-only API, identity, append-only history, training/checkpoint semantics, and provenance.

## Destination acceptance order

1. Reconstruct/version Lantern's own admitted hosted baseline.
2. Classify each dormant construction-era object as RETAIN / REBUILD / QUARANTINE / RETIRE-CANDIDATE / UNKNOWN.
3. Admit a source-controlled BT2 destination schema/API contract.
4. Validate source and destination security semantics before data copy.
5. Import a bound BT2 data snapshot and verify deterministic data/invariant digests.
6. Cut BT2 writers and readers only after the destination is proven.
7. Keep Lantern's project-local data and BT2 project-local data separated by explicit ownership even though they share one Supabase project.
8. Retire stale construction objects only through a separate evidence-and-authorization path.

## Clean target principle

The goal is not an empty database. The goal is a database where every live object has an owner, semantic class, reproducible source, writer/reader path, retention rule, security boundary, and recovery story.
