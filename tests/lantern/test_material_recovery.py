from lantern.material_runtime import *
from lantern.material_universe import *
def test_witness_bounded_and_movement_unknown():
 dg,n=visible_set_digest([])
 c=Cut("prof",dg,n); w=Witness("p","prof",dg,n,None)
 assert evaluate_recovery(project_scope="p",read_cut=lambda:c,read_materials=lambda:[],read_witness=lambda:w)=="WITNESS_BOUNDED"
 seq=iter([c,Cut("other",dg,n)])
 assert evaluate_recovery(project_scope="p",read_cut=lambda:next(seq),read_materials=lambda:[],read_witness=lambda:w)=="UNKNOWN"
def test_no_witness_is_lineage_local():
 dg,n=visible_set_digest([]); c=Cut("p",dg,n)
 assert evaluate_recovery(project_scope="p",read_cut=lambda:c,read_materials=lambda:[],read_witness=lambda:None)=="LINEAGE_LOCAL"
