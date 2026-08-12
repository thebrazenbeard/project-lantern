from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Sequence
from .material_universe import Material, visible_set_digest

@dataclass(frozen=True)
class Cut:
    profile_digest:str
    material_digest:str
    material_count:int

@dataclass(frozen=True)
class Witness:
    project_scope:str
    profile_digest:str
    material_digest:str
    material_count:int
    predecessor_witness_digest:str|None

def evaluate_recovery(*, project_scope:str, read_cut:Callable[[],Cut],
                      read_materials:Callable[[],Sequence[Material]],
                      read_witness:Callable[[],Witness|None]) -> str:
    b0=read_cut()
    materials=read_materials()
    derived,count=visible_set_digest(materials)
    if (derived,count)!=(b0.material_digest,b0.material_count): return "UNKNOWN"
    witness=read_witness()
    b1=read_cut()
    if b0!=b1: return "UNKNOWN"
    if witness is None: return "LINEAGE_LOCAL"
    if (witness.project_scope!=project_scope or witness.profile_digest!=b0.profile_digest
        or witness.material_digest!=b0.material_digest or witness.material_count!=b0.material_count):
        return "UNKNOWN"
    return "WITNESS_BOUNDED"
