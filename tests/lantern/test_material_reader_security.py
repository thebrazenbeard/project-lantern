import re
from pathlib import Path

from lantern.material_universe import MaterialUnknown, resolve_current_profile

SQL=Path('projects/lantern/sql/001_material_universe_v1.sql').read_text()
CUT=Path('projects/lantern/sql/bootstrap_material_cut_v1.sql').read_text()
APPEND=SQL.split('CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(',1)[1].split('END $$;',1)[0]
HELPER=SQL.split('CREATE OR REPLACE FUNCTION lantern_material.assert_no_duplicate_json_keys_v1',1)[1].split('CREATE OR REPLACE FUNCTION lantern_material.append_material_v1',1)[0]


def profile(digest, predecessor=None, *, accepted=True, scope='p', policy='policy'):
    return {'project_scope':scope,'profile_digest':digest,'predecessor_digest':predecessor,'policy_digest':policy,'accepted':accepted}


def assert_unknown(rows):
    try:
        resolve_current_profile(rows,'p')
    except MaterialUnknown:
        return
    raise AssertionError('fixture must be rejected by Python authority')


def test_runtime_never_uses_generic_memory_events():
    assert 'memory_events is qualified seed/import provenance only' in SQL and 'memory_events' not in CUT


def test_composite_authority_crossbind():
    assert 'FOREIGN KEY(grant_id,project_scope,producer_principal,schema_version,profile_digest,policy_digest)' in SQL
    assert 'JOIN lantern_material.producer_grant g' in SQL


def test_append_caller_cannot_select_profile_or_policy():
    sig=SQL.split('CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(',1)[1].split(') RETURNS',1)[0]
    assert 'p_profile_digest' not in sig and 'p_policy_digest' not in sig


def test_duplicate_keys_checked_before_jsonb():
    assert 'payload_json:=p_payload_text::json; PERFORM lantern_material.assert_no_duplicate_json_keys_v1(payload_json); payload_jsonb:=payload_json::jsonb;' in APPEND


def test_profile_lineage_and_seed_receipt_materialized():
    assert 'accepted_profile_one_child_v1' in SQL and 'seed_import_receipt' in SQL


def test_target_unbound():
    assert 'DEPLOYMENT_BINDING_UNBOUND' in SQL


def test_lineage_resolver_shape_is_shared_by_append_and_cut():
    required=(
        'WITH RECURSIVE scoped AS MATERIALIZED',
        'genesis_count=1',
        'self_count=0',
        'orphan_count=0',
        'NOT EXISTS(SELECT 1 FROM forks)',
        '(SELECT count(*) FROM walk)=st.total',
        '(SELECT count(*) FROM leaves)=1',
    )
    assert APPEND.count('WITH RECURSIVE scoped AS MATERIALIZED') == 2
    for token in required:
        assert token in APPEND
        assert token in CUT


def test_l01_l02_valid_profile_shapes_match_python_and_sql_contract():
    genesis=[profile('G')]
    linear=[profile('G'),profile('A','G'),profile('B','A')]
    assert resolve_current_profile(genesis,'p')['profile_digest']=='G'
    assert resolve_current_profile(linear,'p')['profile_digest']=='B'
    assert 'FROM leaves l CROSS JOIN stats st' in APPEND and 'FROM leaves l CROSS JOIN stats st' in CUT


def test_l03_l08_invalid_profile_shapes_are_bound_to_fail_closed_predicates():
    invalid=[
        [],
        [profile('O','missing')],
        [profile('G'),profile('A','G'),profile('B','A'),profile('C','D'),profile('D','C')],
        [profile('A','B'),profile('B','A')],
        [profile('G'),profile('A','G'),profile('B','G')],
        [profile('G1'),profile('G2')],
        [profile('G'),profile('G')],
    ]
    for rows in invalid:
        assert_unknown(rows)
    assert 'PRIMARY KEY(project_scope,profile_digest)' in SQL
    assert 'accepted_profile_one_genesis_v1' in SQL
    assert 'accepted_profile_one_child_v1' in SQL


def test_i01_i02_read_committed_guard_precedes_first_profile_read():
    guard=APPEND.index("current_setting('transaction_isolation')")
    first_profile=APPEND.index('lantern_material.accepted_profile')
    assert guard < first_profile
    assert "lower(current_setting('transaction_isolation')) <> 'read committed'" in APPEND


def test_c01_c02_serialization_and_post_lock_revalidation_order():
    resolvers=[m.start() for m in re.finditer('WITH RECURSIVE scoped AS MATERIALIZED',APPEND)]
    lock=APPEND.index('LOCK TABLE lantern_material.accepted_profile IN SHARE MODE')
    compare=APPEND.index('locked_lineage IS DISTINCT FROM pre_lineage')
    grant=APPEND.index('SELECT * INTO STRICT g FROM lantern_material.producer_grant')
    assert len(resolvers)==2 and resolvers[0] < lock < resolvers[1] < compare < grant
    assert 'locked_profile_digest IS DISTINCT FROM pre_profile_digest' in APPEND
    assert "RAISE EXCEPTION 'accepted profile lineage changed during admission'" in APPEND


def test_sec01_append_signature_security_search_path_and_public_acl():
    sig=SQL.split('CREATE OR REPLACE FUNCTION lantern_material.append_material_v1(',1)[1].split(') RETURNS',1)[0]
    assert sig.count(',')==5
    assert 'RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,lantern_material' in SQL
    assert 'REVOKE ALL ON FUNCTION lantern_material.append_material_v1(uuid,text,text,text,text,text) FROM PUBLIC;' in SQL


def test_sec02_duplicate_key_helper_security_mutability_and_ordering():
    assert 'LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$' in HELPER
    assert 'SECURITY DEFINER' not in HELPER
    assert APPEND.index('assert_no_duplicate_json_keys_v1(payload_json)') < APPEND.index('payload_jsonb:=payload_json::jsonb')


def test_sec03_portable_sha_is_preserved_and_digest_function_is_absent():
    assert APPEND.count('pg_catalog.sha256(')==2
    assert APPEND.count('pg_catalog.encode(')==2
    assert re.search(r'(?<!sha256)\bdigest\s*\(',APPEND,re.IGNORECASE) is None


def test_s01_s02_semantic_identity_uniqueness_not_weakened():
    assert 'UNIQUE(project_scope,schema_version,semantic_key)' in SQL
    assert 'INSERT INTO lantern_material.material VALUES' in APPEND
    assert 'ON CONFLICT' not in APPEND
