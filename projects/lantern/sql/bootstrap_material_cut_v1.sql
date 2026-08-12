-- LANTERN_MATERIAL_CUT_V1: execute this single statement in one READ ONLY snapshot for each B0/B1 cut.
WITH current_profile AS (
 SELECT p.project_scope,p.profile_digest,p.predecessor_digest,p.policy_digest
 FROM lantern_material.accepted_profile p
 WHERE p.project_scope=$1 AND p.accepted AND NOT EXISTS(
  SELECT 1 FROM lantern_material.accepted_profile c WHERE c.project_scope=p.project_scope AND c.accepted AND c.predecessor_digest=p.profile_digest)
), members AS (
 SELECT m.material_id::text AS material_id,m.canonical_digest,m.semantic_key,m.source_digest
 FROM lantern_material.runtime_visible_v1 m JOIN current_profile p ON p.project_scope=m.project_scope AND p.profile_digest=m.profile_digest
 ORDER BY m.material_id
)
SELECT 'LANTERN_MATERIAL_CUT_V1'::text AS facade_id,p.profile_digest,p.predecessor_digest,p.policy_digest,
 coalesce(json_agg(json_build_array(x.material_id,x.canonical_digest,x.semantic_key,x.source_digest) ORDER BY x.material_id) FILTER (WHERE x.material_id IS NOT NULL),'[]'::json) AS exact_members,
 count(x.material_id)::bigint AS material_count
FROM current_profile p LEFT JOIN members x ON true GROUP BY p.profile_digest,p.predecessor_digest,p.policy_digest
HAVING (SELECT count(*) FROM current_profile)=1;
