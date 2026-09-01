-- LANTERN_MATERIAL_UNIVERSE_V1. Target binding: DEPLOYMENT_BINDING_UNBOUND.
-- build_team_2.memory_events is qualified seed/import provenance only; ordinary runtime never reads it.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS lantern_material;

CREATE TABLE lantern_material.schema_policy(
 schema_version text PRIMARY KEY, canonicalizer_digest text NOT NULL,
 semantic_projector_digest text NOT NULL, semantic_fields text[] NOT NULL CHECK(cardinality(semantic_fields)>0)
);
CREATE TABLE lantern_material.accepted_profile(
 project_scope text NOT NULL, profile_digest text NOT NULL, predecessor_digest text,
 policy_digest text NOT NULL, accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(), accepted boolean NOT NULL DEFAULT true,
 PRIMARY KEY(project_scope,profile_digest), CHECK(predecessor_digest IS NULL OR predecessor_digest<>profile_digest)
);
CREATE UNIQUE INDEX accepted_profile_one_genesis_v1 ON lantern_material.accepted_profile(project_scope) WHERE accepted AND predecessor_digest IS NULL;
CREATE UNIQUE INDEX accepted_profile_one_child_v1 ON lantern_material.accepted_profile(project_scope,predecessor_digest) WHERE accepted AND predecessor_digest IS NOT NULL;
CREATE TABLE lantern_material.producer_grant(
 grant_id uuid PRIMARY KEY, project_scope text NOT NULL, producer_principal text NOT NULL,
 schema_version text NOT NULL, profile_digest text NOT NULL, policy_digest text NOT NULL,
 valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL, revoked_at timestamptz,
 UNIQUE(grant_id,project_scope,producer_principal,schema_version,profile_digest,policy_digest)
);
CREATE TABLE lantern_material.material(
 material_id uuid PRIMARY KEY, project_scope text NOT NULL, schema_version text NOT NULL,
 semantic_key text NOT NULL, canonical_digest text NOT NULL, source_digest text NOT NULL,
 canonical_payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(project_scope,schema_version,semantic_key)
);
CREATE TABLE lantern_material.admission_receipt(
 receipt_id uuid PRIMARY KEY, material_id uuid NOT NULL UNIQUE REFERENCES lantern_material.material(material_id),
 project_scope text NOT NULL, producer_principal text NOT NULL, grant_id uuid NOT NULL,
 profile_digest text NOT NULL, policy_digest text NOT NULL, schema_version text NOT NULL,
 semantic_key text NOT NULL, canonical_digest text NOT NULL, source_digest text NOT NULL,
 admitted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(grant_id,project_scope,producer_principal,schema_version,profile_digest,policy_digest)
 REFERENCES lantern_material.producer_grant(grant_id,project_scope,producer_principal,schema_version,profile_digest,policy_digest)
);
CREATE TABLE lantern_material.seed_import_receipt(
 source_collective_id text NOT NULL, source_event_id text NOT NULL, source_reducer_digest text NOT NULL,
 semantic_role text NOT NULL, imported_material_digest text NOT NULL,
 material_id uuid NOT NULL UNIQUE REFERENCES lantern_material.material(material_id), imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(source_collective_id,source_event_id)
);
REVOKE ALL ON lantern_material.material,lantern_material.admission_receipt,lantern_material.seed_import_receipt FROM PUBLIC;

CREATE OR REPLACE FUNCTION lantern_material.assert_no_duplicate_json_keys_v1(j json) RETURNS void
LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE v json;
BEGIN
 IF json_typeof(j)='object' THEN
   IF EXISTS(SELECT 1 FROM json_each(j) GROUP BY key HAVING count(*)>1) THEN RAISE EXCEPTION 'duplicate JSON key'; END IF;
   FOR v IN SELECT value FROM json_each(j) LOOP PERFORM lantern_material.assert_no_duplicate_json_keys_v1(v); END LOOP;
 ELSIF json_typeof(j)='array' THEN
   FOR v IN SELECT value FROM json_array_elements(j) LOOP PERFORM lantern_material.assert_no_duplicate_json_keys_v1(v); END LOOP;
 END IF;
END $$;

CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(
 p_material_id uuid,p_project_scope text,p_producer_principal text,p_schema_version text,
 p_source_digest text,p_payload_text text
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,lantern_material AS $$
DECLARE
 g lantern_material.producer_grant%ROWTYPE; sp lantern_material.schema_policy%ROWTYPE;
 payload_json json; payload_jsonb jsonb; rid uuid; sk text; cd text;
 pre_profile_digest text; pre_predecessor_digest text; pre_policy_digest text; pre_lineage jsonb;
 locked_profile_digest text; locked_predecessor_digest text; locked_policy_digest text; locked_lineage jsonb;
BEGIN
 IF lower(current_setting('transaction_isolation')) <> 'read committed' THEN
   RAISE EXCEPTION 'append_material_v1 requires READ COMMITTED transaction isolation';
 END IF;
 payload_json:=p_payload_text::json; PERFORM lantern_material.assert_no_duplicate_json_keys_v1(payload_json); payload_jsonb:=payload_json::jsonb;
 SELECT * INTO STRICT sp FROM lantern_material.schema_policy WHERE schema_version=p_schema_version;

 WITH RECURSIVE scoped AS MATERIALIZED (
   SELECT p.project_scope,p.profile_digest,p.predecessor_digest,p.policy_digest
   FROM lantern_material.accepted_profile p WHERE p.project_scope=p_project_scope AND p.accepted
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
   SELECT gen.project_scope,gen.profile_digest,gen.predecessor_digest,gen.policy_digest,ARRAY[gen.profile_digest]::text[] AS path
   FROM genesis gen
   UNION ALL
   SELECT c.project_scope,c.profile_digest,c.predecessor_digest,c.policy_digest,w.path||c.profile_digest
   FROM walk w JOIN scoped c ON c.predecessor_digest=w.profile_digest
   WHERE NOT c.profile_digest=ANY(w.path)
 ), leaves AS (
   SELECT s.* FROM scoped s WHERE NOT EXISTS(SELECT 1 FROM scoped c WHERE c.predecessor_digest=s.profile_digest)
 ), valid AS (
   SELECT l.*,(SELECT jsonb_agg(jsonb_build_array(s.profile_digest,s.predecessor_digest,s.policy_digest) ORDER BY s.profile_digest) FROM scoped s) AS lineage
   FROM leaves l CROSS JOIN stats st
   WHERE st.total>0 AND st.genesis_count=1 AND st.self_count=0 AND st.orphan_count=0
     AND NOT EXISTS(SELECT 1 FROM forks)
     AND (SELECT count(*) FROM walk)=st.total
     AND (SELECT count(*) FROM leaves)=1
 )
 SELECT v.profile_digest,v.predecessor_digest,v.policy_digest,v.lineage
 INTO pre_profile_digest,pre_predecessor_digest,pre_policy_digest,pre_lineage FROM valid v;
 IF pre_profile_digest IS NULL THEN RAISE EXCEPTION 'accepted profile lineage is invalid'; END IF;

 LOCK TABLE lantern_material.accepted_profile IN SHARE MODE;

 WITH RECURSIVE scoped AS MATERIALIZED (
   SELECT p.project_scope,p.profile_digest,p.predecessor_digest,p.policy_digest
   FROM lantern_material.accepted_profile p WHERE p.project_scope=p_project_scope AND p.accepted
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
   SELECT gen.project_scope,gen.profile_digest,gen.predecessor_digest,gen.policy_digest,ARRAY[gen.profile_digest]::text[] AS path
   FROM genesis gen
   UNION ALL
   SELECT c.project_scope,c.profile_digest,c.predecessor_digest,c.policy_digest,w.path||c.profile_digest
   FROM walk w JOIN scoped c ON c.predecessor_digest=w.profile_digest
   WHERE NOT c.profile_digest=ANY(w.path)
 ), leaves AS (
   SELECT s.* FROM scoped s WHERE NOT EXISTS(SELECT 1 FROM scoped c WHERE c.predecessor_digest=s.profile_digest)
 ), valid AS (
   SELECT l.*,(SELECT jsonb_agg(jsonb_build_array(s.profile_digest,s.predecessor_digest,s.policy_digest) ORDER BY s.profile_digest) FROM scoped s) AS lineage
   FROM leaves l CROSS JOIN stats st
   WHERE st.total>0 AND st.genesis_count=1 AND st.self_count=0 AND st.orphan_count=0
     AND NOT EXISTS(SELECT 1 FROM forks)
     AND (SELECT count(*) FROM walk)=st.total
     AND (SELECT count(*) FROM leaves)=1
 )
 SELECT v.profile_digest,v.predecessor_digest,v.policy_digest,v.lineage
 INTO locked_profile_digest,locked_predecessor_digest,locked_policy_digest,locked_lineage FROM valid v;
 IF locked_profile_digest IS NULL THEN RAISE EXCEPTION 'accepted profile lineage is invalid after serialization'; END IF;
 IF locked_profile_digest IS DISTINCT FROM pre_profile_digest
    OR locked_predecessor_digest IS DISTINCT FROM pre_predecessor_digest
    OR locked_policy_digest IS DISTINCT FROM pre_policy_digest
    OR locked_lineage IS DISTINCT FROM pre_lineage THEN
   RAISE EXCEPTION 'accepted profile lineage changed during admission';
 END IF;

 SELECT * INTO STRICT g FROM lantern_material.producer_grant
 WHERE project_scope=p_project_scope AND producer_principal=p_producer_principal AND schema_version=p_schema_version
   AND profile_digest=locked_profile_digest AND policy_digest=locked_policy_digest AND revoked_at IS NULL
   AND valid_from<=clock_timestamp() AND valid_until>clock_timestamp() FOR SHARE;
 IF sp.semantic_fields<>ARRAY['semantic_role','subject_key']::text[] OR NOT(payload_jsonb?'semantic_role' AND payload_jsonb?'subject_key') THEN
   RAISE EXCEPTION 'unknown or incomplete semantic projector'; END IF;
 sk:=pg_catalog.encode(pg_catalog.sha256(convert_to(jsonb_build_array(payload_jsonb->'semantic_role',payload_jsonb->'subject_key')::text,'UTF8')),'hex');
 cd:=pg_catalog.encode(pg_catalog.sha256(convert_to(payload_jsonb::text,'UTF8')),'hex');
 INSERT INTO lantern_material.material VALUES(p_material_id,p_project_scope,p_schema_version,sk,cd,p_source_digest,payload_jsonb,clock_timestamp());
 rid:=gen_random_uuid();
 INSERT INTO lantern_material.admission_receipt(receipt_id,material_id,project_scope,producer_principal,grant_id,profile_digest,policy_digest,schema_version,semantic_key,canonical_digest,source_digest)
 VALUES(rid,p_material_id,p_project_scope,p_producer_principal,g.grant_id,locked_profile_digest,locked_policy_digest,p_schema_version,sk,cd,p_source_digest);
 RETURN rid;
END $$;
REVOKE ALL ON FUNCTION lantern_material.append_material_v1(uuid,text,text,text,text,text) FROM PUBLIC;

CREATE VIEW lantern_material.runtime_visible_v1 AS
 SELECT m.*,r.receipt_id,r.profile_digest,r.policy_digest
 FROM lantern_material.material m
 JOIN lantern_material.admission_receipt r ON r.material_id=m.material_id AND r.project_scope=m.project_scope AND r.schema_version=m.schema_version
  AND r.semantic_key=m.semantic_key AND r.canonical_digest=m.canonical_digest AND r.source_digest=m.source_digest
 JOIN lantern_material.producer_grant g ON (g.grant_id,g.project_scope,g.producer_principal,g.schema_version,g.profile_digest,g.policy_digest)=
  (r.grant_id,r.project_scope,r.producer_principal,r.schema_version,r.profile_digest,r.policy_digest);
