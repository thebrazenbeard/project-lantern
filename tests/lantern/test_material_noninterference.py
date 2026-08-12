from lantern.material_runtime import *
from lantern.material_universe import visible_set_digest
def test_observation_b0_b1_same():
 dg,n=visible_set_digest([]); c=Cut("p",dg,n); calls=[]
 def cut(): calls.append(c); return c
 assert evaluate_recovery(project_scope="p",read_cut=cut,read_materials=lambda:[],read_witness=lambda:None)=="LINEAGE_LOCAL"
 assert calls==[c,c]
def test_observation_movement_unknown():
 dg,n=visible_set_digest([]); cuts=iter([Cut("a",dg,n),Cut("b",dg,n)])
 assert evaluate_recovery(project_scope="p",read_cut=lambda:next(cuts),read_materials=lambda:[],read_witness=lambda:None)=="UNKNOWN"
