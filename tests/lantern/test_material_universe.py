import pytest
from lantern.material_universe import *
P=SchemaPolicy("v1","canon","projector",("semantic_role","subject_key"))
def mk(i="1",payload=None):
 return build_material(project_scope="p",material_id=i,schema_version="v1",payload=payload or {"semantic_role":"fact","subject_key":"x","v":1},source_digest="s",policies={"v1":P})
def test_unknown_schema_fails():
 with pytest.raises(MaterialUnknown): build_material(project_scope="p",material_id="1",schema_version="x",payload={},source_digest="s",policies={})
def test_semantic_identity_verifier_derived(): assert mk().semantic_key==mk("2").semantic_key
def test_profile_chain_unique_leaf():
 ps=[{"project_scope":"p","profile_digest":"a","predecessor_digest":None,"accepted":True},{"project_scope":"p","profile_digest":"b","predecessor_digest":"a","accepted":True}]
 assert resolve_current_profile(ps,"p")["profile_digest"]=="b"
def test_profile_fork_unknown():
 ps=[{"project_scope":"p","profile_digest":"a","predecessor_digest":None,"accepted":True},{"project_scope":"p","profile_digest":"b","predecessor_digest":"a","accepted":True},{"project_scope":"p","profile_digest":"c","predecessor_digest":"a","accepted":True}]
 with pytest.raises(MaterialUnknown): resolve_current_profile(ps,"p")
