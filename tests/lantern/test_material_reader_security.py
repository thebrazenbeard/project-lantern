from pathlib import Path
SQL=Path('projects/lantern/sql/001_material_universe_v1.sql').read_text()
CUT=Path('projects/lantern/sql/bootstrap_material_cut_v1.sql').read_text()
def test_runtime_never_uses_generic_memory_events(): assert 'memory_events is qualified seed/import provenance only' in SQL and 'memory_events' not in CUT
def test_composite_authority_crossbind(): assert 'FOREIGN KEY(grant_id,project_scope,producer_principal,schema_version,profile_digest,policy_digest)' in SQL and 'JOIN lantern_material.producer_grant g' in SQL
def test_append_caller_cannot_select_profile_or_policy():
 sig=SQL.split('CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(',1)[1].split(') RETURNS',1)[0]
 assert 'p_profile_digest' not in sig and 'p_policy_digest' not in sig
def test_duplicate_keys_checked_before_jsonb(): assert 'payload_json:=p_payload_text::json; PERFORM lantern_material.assert_no_duplicate_json_keys_v1(payload_json); payload_jsonb:=payload_json::jsonb;' in SQL
def test_profile_lineage_and_seed_receipt_materialized(): assert 'accepted_profile_one_child_v1' in SQL and 'seed_import_receipt' in SQL
def test_target_unbound(): assert 'DEPLOYMENT_BINDING_UNBOUND' in SQL
