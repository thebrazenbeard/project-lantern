-- LANTERN_MATERIAL_UNIVERSE_V1. Target binding: DEPLOYMENT_BINDING_UNBOUND.
-- Generic build_team_2.memory_events is import provenance only; runtime queries never read it.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS lantern_material;

CREATE TABLE lantern_material.schema_policy (
  schema_version text PRIMARY KEY, canonicalizer_digest text NOT NULL,
  semantic_projector_digest text NOT NULL, semantic_fields text[] NOT NULL CHECK(cardinality(semantic_fields)>0)
);

CREATE TABLE lantern_material.producer_grant (
  grant_id uuid PRIMARY KEY, project_scope text NOT NULL, producer_principal text NOT NULL,
  schema_version text NOT NULL, profile_digest text NOT NULL, policy_digest text NOT NULL,
  valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL, revoked_at timestamptz,
  UNIQUE(project_scope,producer_principal,schema_version,profile_digest,policy_digest,valid_from)
);
CREATE TABLE lantern_material.material (
  material_id uuid PRIMARY KEY, project_scope text NOT NULL, schema_version text NOT NULL,
  semantic_key text NOT NULL, canonical_digest text NOT NULL, source_digest text NOT NULL,
  canonical_payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(project_scope,schema_version,semantic_key)
);
CREATE TABLE lantern_material.admission_receipt (
  receipt_id uuid PRIMARY KEY, material_id uuid NOT NULL UNIQUE REFERENCES lantern_material.material(material_id),
  project_scope text NOT NULL, producer_principal text NOT NULL, grant_id uuid NOT NULL REFERENCES lantern_material.producer_grant(grant_id),
  profile_digest text NOT NULL, policy_digest text NOT NULL, schema_version text NOT NULL,
  semantic_key text NOT NULL, canonical_digest text NOT NULL, source_digest text NOT NULL,
  admitted_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON lantern_material.material, lantern_material.admission_receipt FROM PUBLIC;

CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(
 p_material_id uuid,p_project_scope text,p_producer_principal text,p_schema_version text,
 p_source_digest text,p_payload jsonb,p_profile_digest text,p_policy_digest text
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,lantern_material AS $$
DECLARE g lantern_material.producer_grant%ROWTYPE; sp lantern_material.schema_policy%ROWTYPE;
 rid uuid; sk text; cd text;
BEGIN
 SELECT * INTO STRICT sp FROM lantern_material.schema_policy WHERE schema_version=p_schema_version;
 IF sp.semantic_fields <> ARRAY['semantic_role','subject_key']::text[] THEN
   RAISE EXCEPTION 'unknown semantic projector for schema %',p_schema_version;
 END IF;
 IF NOT (p_payload ? 'semantic_role' AND p_payload ? 'subject_key') THEN
   RAISE EXCEPTION 'required semantic identity fields absent';
 END IF;
 sk=encode(digest(convert_to(jsonb_build_object('semantic_role',p_payload->'semantic_role','subject_key',p_payload->'subject_key')::text,'UTF8'),'sha256'),'hex');
 cd=encode(digest(convert_to(p_payload::text,'UTF8'),'sha256'),'hex');
 SELECT * INTO STRICT g FROM lantern_material.producer_grant
 WHERE project_scope=p_project_scope AND producer_principal=p_producer_principal
   AND schema_version=p_schema_version AND profile_digest=p_profile_digest AND policy_digest=p_policy_digest
   AND revoked_at IS NULL AND valid_from<=clock_timestamp() AND valid_until>clock_timestamp()
 FOR SHARE;
 INSERT INTO lantern_material.material(material_id,project_scope,schema_version,semantic_key,canonical_digest,source_digest,canonical_payload)
 VALUES(p_material_id,p_project_scope,p_schema_version,sk,cd,p_source_digest,p_payload);
 rid=gen_random_uuid();
 INSERT INTO lantern_material.admission_receipt(receipt_id,material_id,project_scope,producer_principal,grant_id,profile_digest,policy_digest,schema_version,semantic_key,canonical_digest,source_digest)
 VALUES(rid,p_material_id,p_project_scope,p_producer_principal,g.grant_id,p_profile_digest,p_policy_digest,p_schema_version,sk,cd,p_source_digest);
 RETURN rid;
END $$;
REVOKE ALL ON FUNCTION lantern_material.append_material_v1(uuid,text,text,text,text,jsonb,text,text) FROM PUBLIC;

CREATE VIEW lantern_material.runtime_visible_v1 AS
 SELECT m.*,r.receipt_id,r.profile_digest,r.policy_digest
 FROM lantern_material.material m JOIN lantern_material.admission_receipt r
 ON r.material_id=m.material_id AND r.project_scope=m.project_scope AND r.schema_version=m.schema_version
 AND r.semantic_key=m.semantic_key AND r.canonical_digest=m.canonical_digest AND r.source_digest=m.source_digest;
