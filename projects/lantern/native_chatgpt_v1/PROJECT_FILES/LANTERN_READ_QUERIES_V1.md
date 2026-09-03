# LANTERN_READ_QUERIES_V1

These are **read-only** connector queries for the exact Lantern Supabase target `agvhmutlrolbaijzlbqk`.

The B0/B1 cut below is the checked-in `bootstrap_material_cut_v1.sql` at blob `f1fe273172d284d84ab7f10922d5a974a79fe2f2` with only its `$1` project-scope parameter bound to the literal `PROJECT_LANTERN`.

## B0 / B1 — governed material cut

```sql
WITH RECURSIVE scoped AS MATERIALIZED (
 SELECT p.project_scope,p.profile_digest,p.predecessor_digest,p.policy_digest
 FROM lantern_material.accepted_profile p WHERE p.project_scope='PROJECT_LANTERN' AND p.accepted
), stats AS (
 SELECT count(*)::int AS total,
  count(*) FILTER (WHERE predecessor_digest IS NULL)::int AS genesis_count,
  count(*) FILTER (WHERE predecessor_digest IS NOT NULL AND predecessor_digest=profile_digest)::int AS self_count,
  count(*) FILTER (WHERE predecessor_digest IS NOT NULL AND NOT EXISTS(
   SELECT 1 FROM scoped parent WHERE parent.profile_digest=scoped.predecessor_digest))::int AS orphan_count
 FROM scoped
), forks AS (
 SELECT predecessor_digest FROM scoped WHERE predecessor_digest IS NOT NULL
 GROUP BY predecessor_digest HAVING count(*)>1
), genesis AS (
 SELECT * FROM scoped WHERE predecessor_digest IS NULL
), walk AS (
 SELECT g.project_scope,g.profile_digest,g.predecessor_digest,g.policy_digest,ARRAY[g.profile_digest]::text[] AS path
 FROM genesis g
 UNION ALL
 SELECT c.project_scope,c.profile_digest,c.predecessor_digest,c.policy_digest,w.path||c.profile_digest
 FROM walk w JOIN scoped c ON c.predecessor_digest=w.profile_digest
 WHERE NOT c.profile_digest=ANY(w.path)
), leaves AS (
 SELECT s.* FROM scoped s WHERE NOT EXISTS(SELECT 1 FROM scoped c WHERE c.predecessor_digest=s.profile_digest)
), current_profile AS (
 SELECT l.project_scope,l.profile_digest,l.predecessor_digest,l.policy_digest
 FROM leaves l CROSS JOIN stats st
 WHERE st.total>0 AND st.genesis_count=1 AND st.self_count=0 AND st.orphan_count=0
  AND NOT EXISTS(SELECT 1 FROM forks)
  AND (SELECT count(*) FROM walk)=st.total
  AND (SELECT count(*) FROM leaves)=1
), members AS (
 SELECT m.material_id::text AS material_id,m.canonical_digest,m.semantic_key,m.source_digest
 FROM lantern_material.runtime_visible_v1 m JOIN current_profile p ON p.project_scope=m.project_scope AND p.profile_digest=m.profile_digest
 ORDER BY m.material_id
)
SELECT 'LANTERN_MATERIAL_CUT_V1'::text AS facade_id,p.profile_digest,p.predecessor_digest,p.policy_digest,
 coalesce(json_agg(json_build_array(x.material_id,x.canonical_digest,x.semantic_key,x.source_digest) ORDER BY x.material_id) FILTER (WHERE x.material_id IS NOT NULL),'[]'::json) AS exact_members,
 count(x.material_id)::bigint AS material_count
FROM current_profile p LEFT JOIN members x ON true GROUP BY p.profile_digest,p.predecessor_digest,p.policy_digest;
```

Expected shape: exactly one row with `facade_id = LANTERN_MATERIAL_CUT_V1`, profile/policy digests, `exact_members`, and `material_count`. Zero rows means the accepted-profile lineage did not produce an authoritative current cut; fail closed.

## Payload fetch between B0 and B1

```sql
SELECT material_id::text, project_scope, schema_version, semantic_key,
       canonical_digest, source_digest, canonical_payload, created_at,
       receipt_id::text, profile_digest, policy_digest
FROM lantern_material.runtime_visible_v1
WHERE project_scope='PROJECT_LANTERN'
ORDER BY material_id;
```

Cross-bind the payload result to B0:
- result row count == B0 `material_count`;
- each result row contributes `[material_id, canonical_digest, semantic_key, source_digest]`;
- the sorted set of those four-tuples exactly equals B0 `exact_members`;
- each result `profile_digest` and `policy_digest` equals the B0 profile/policy.

Then execute B1. B1 must exactly equal B0. Retry the whole B0→payload→B1 sequence once on mismatch; a second mismatch is `UNKNOWN`.

Do not use these read queries as authority for writes.
