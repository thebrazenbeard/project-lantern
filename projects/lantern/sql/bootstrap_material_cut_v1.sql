-- Execute in one READ ONLY transaction for both B0 and B1.
SELECT r.profile_digest,
       encode(digest(coalesce(string_agg(m.material_id::text || ':' || m.canonical_digest || ':' || m.semantic_key, ',' ORDER BY m.material_id),''),'sha256'),'hex') AS material_digest,
       count(m.material_id)::bigint AS material_count
FROM lantern_material.runtime_visible_v1 m
JOIN lantern_material.admission_receipt r ON r.material_id=m.material_id
WHERE m.project_scope = $1
GROUP BY r.profile_digest;
