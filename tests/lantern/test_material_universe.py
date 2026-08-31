import pytest
from lantern.material_universe import *

P=SchemaPolicy('v1','canon','projector',('semantic_role','subject_key'))


def mk(i='1',payload=None,source='s'):
 return build_material(project_scope='p',material_id=i,schema_version='v1',payload=payload or {'semantic_role':'fact','subject_key':'x','v':1},source_digest=source,policies={'v1':P})


def prof(digest, predecessor=None, *, accepted=True, scope='p'):
 return {'project_scope':scope,'profile_digest':digest,'predecessor_digest':predecessor,'accepted':accepted}


def rejects(rows):
 with pytest.raises(MaterialUnknown): resolve_current_profile(rows,'p')


def test_unknown_schema_fails():
 with pytest.raises(MaterialUnknown): build_material(project_scope='p',material_id='1',schema_version='x',payload={},source_digest='s',policies={})


def test_duplicate_json_keys_fail_before_materialization():
 with pytest.raises(Exception): build_material(project_scope='p',material_id='1',schema_version='v1',payload_text='{"semantic_role":"f","subject_key":"x","subject_key":"y"}',source_digest='s',policies={'v1':P})


def test_semantic_identity_verifier_derived(): assert mk().semantic_key==mk('2').semantic_key


def test_l01_genesis_only_selects_genesis():
 assert resolve_current_profile([prof('G')],'p')['profile_digest']=='G'


def test_l02_linear_chain_selects_terminal_b():
 ps=[prof('G'),prof('A','G'),prof('B','A')]
 assert resolve_current_profile(ps,'p')['profile_digest']=='B'


def test_l03_no_accepted_profile_unknown():
 rejects([])
 rejects([prof('G',accepted=False)])


def test_l04_missing_predecessor_and_disconnected_set_unknown():
 rejects([prof('G'),prof('orphan','missing')])
 rejects([prof('G'),prof('A','G'),prof('C','D'),prof('D','C')])


def test_l05_cycle_unknown():
 rejects([prof('A','B'),prof('B','A')])
 rejects([prof('G'),prof('A','G'),prof('C','D'),prof('D','C')])


def test_l06_profile_fork_unknown():
 ps=[prof('G'),prof('A','G'),prof('B','G')]
 rejects(ps)


def test_l07_nonunique_genesis_or_current_leaf_unknown():
 rejects([prof('G1'),prof('G2')])
 rejects([prof('G'),prof('A','G'),prof('B','G')])


def test_l08_duplicate_profile_digest_unknown():
 rejects([prof('G'),prof('G')])


def test_self_predecessor_unknown():
 rejects([prof('G'),prof('A','A')])


def test_other_scope_does_not_contaminate_current_profile():
 ps=[prof('G'),prof('X',scope='other')]
 assert resolve_current_profile(ps,'p')['profile_digest']=='G'


def test_visible_set_digest_binds_source_digest(): assert visible_set_digest([mk(source='a')])!=visible_set_digest([mk(source='b')])
