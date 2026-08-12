import pytest
from lantern.material_universe import *
P=SchemaPolicy('v1','c','p',('semantic_role','subject_key'))
def m(v=1): return build_material(project_scope='p',material_id='1',schema_version='v1',payload={'semantic_role':'fact','subject_key':'x','v':v},source_digest='s',policies={'v1':P})
def test_absent_create(): assert import_disposition(None,m())=='CREATE'
def test_exact_replay_verified(): assert import_disposition(m(),m())=='VERIFIED'
def test_divergent_same_identity_conflict():
 with pytest.raises(MaterialConflict): import_disposition(m(),m(2))
def test_seed_receipt_replay_and_conflict():
 a=SeedImportReceipt('c','e','r','fact','d','m'); assert seed_import_disposition(None,a)=='CREATE'; assert seed_import_disposition(a,a)=='VERIFIED'
 with pytest.raises(MaterialConflict): seed_import_disposition(a,SeedImportReceipt('c','e','R2','fact','d','m'))
