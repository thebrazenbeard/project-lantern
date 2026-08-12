from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Sequence
from .material_universe import Material, visible_set_digest

@dataclass(frozen=True)
class Cut:
    facade_id:str
    profile_digest:str
    predecessor_profile_digest:str|None
    policy_digest:str
    members:tuple[Material,...]
    material_digest:str
    material_count:int

@dataclass(frozen=True)
class Witness:
    project_scope:str
    profile_digest:str
    predecessor_profile_digest:str|None
    policy_digest:str
    material_digest:str
    material_count:int


def _valid_cut(cut:Cut)->bool:
    digest,count=visible_set_digest(cut.members)
    return digest==cut.material_digest and count==cut.material_count


def _same_snapshot(a:Cut,b:Cut)->bool:
    return a==b and a.facade_id==b.facade_id


def evaluate_recovery(*, project_scope:str, read_cut:Callable[[],Cut],
                      read_witness:Callable[[],Witness|None],
                      read_resource_digest:Callable[[],str]) -> str:
    for attempt in range(2):
        e0=read_resource_digest()
        b0=read_cut()
        if not _valid_cut(b0): return "UNKNOWN"
        witness=read_witness()
        b1=read_cut()
        e1=read_resource_digest()
        if e0!=e1: return "UNKNOWN"
        if not _valid_cut(b1): return "UNKNOWN"
        if not _same_snapshot(b0,b1):
            if attempt==0: continue
            return "UNKNOWN"
        if witness is None: return "LINEAGE_LOCAL"
        if (witness.project_scope!=project_scope or
            witness.profile_digest!=b0.profile_digest or
            witness.predecessor_profile_digest!=b0.predecessor_profile_digest or
            witness.policy_digest!=b0.policy_digest or
            witness.material_digest!=b0.material_digest or
            witness.material_count!=b0.material_count): return "UNKNOWN"
        return "WITNESS_BOUNDED"
    return "UNKNOWN"
