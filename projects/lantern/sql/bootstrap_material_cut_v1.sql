-- LANTERN_MATERIAL_CUT_V1: execute this single statement in one READ ONLY snapshot for each B0/B1 cut.
WITH RECURSIVE scoped AS MATERIALIZED (
 SELECT p.project_scope,p.profile_digest,p.predecessor_digest,p.policy_digest
 FROM lantern_material.accepted_profile p WHERE p.project_scope=$1 AND p.accepted
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
