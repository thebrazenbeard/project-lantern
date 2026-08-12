from lantern.material_runtime import *
from lantern.material_universe import visible_set_digest
def cut():
 m=(); dg,n=visible_set_digest(m); return Cut('LANTERN_MATERIAL_CUT_V1','p',None,'pol',m,dg,n)
def test_observation_e0_e1_same():
 c=cut(); calls=[]
 def rd(): calls.append('r'); return 'same'
 assert evaluate_recovery(project_scope='p',read_cut=lambda:c,read_witness=lambda:None,read_resource_digest=rd)=='LINEAGE_LOCAL'; assert len(calls)==2
def test_observer_attributed_resource_movement_unknown():
 c=cut(); values=iter(['before','after'])
 assert evaluate_recovery(project_scope='p',read_cut=lambda:c,read_witness=lambda:None,read_resource_digest=lambda:next(values))=='UNKNOWN'
