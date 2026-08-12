from lantern.material_runtime import *
from lantern.material_universe import visible_set_digest
def c(profile='prof',pred='pred',policy='pol'):
 members=(); dg,n=visible_set_digest(members); return Cut('LANTERN_MATERIAL_CUT_V1',profile,pred,policy,members,dg,n)
def test_witness_bounded_and_movement_retry():
 stable=c(); w=Witness('p','prof','pred','pol',stable.material_digest,stable.material_count)
 seq=iter([c('old'),stable,stable,stable])
 assert evaluate_recovery(project_scope='p',read_cut=lambda:next(seq),read_witness=lambda:w,read_resource_digest=lambda:'r')=='WITNESS_BOUNDED'
def test_repeat_movement_unknown():
 seq=iter([c('a'),c('b'),c('c'),c('d')])
 assert evaluate_recovery(project_scope='p',read_cut=lambda:next(seq),read_witness=lambda:None,read_resource_digest=lambda:'r')=='UNKNOWN'
def test_no_witness_is_lineage_local(): assert evaluate_recovery(project_scope='p',read_cut=lambda:c(),read_witness=lambda:None,read_resource_digest=lambda:'r')=='LINEAGE_LOCAL'
def test_wrong_predecessor_witness_unknown():
 x=c(); w=Witness('p','prof','wrong','pol',x.material_digest,x.material_count)
 assert evaluate_recovery(project_scope='p',read_cut=lambda:x,read_witness=lambda:w,read_resource_digest=lambda:'r')=='UNKNOWN'
