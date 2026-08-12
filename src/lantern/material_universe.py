from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from .canonical import canonical_json_bytes, sha256_hex

class MaterialError(ValueError): pass
class MaterialConflict(MaterialError): pass
class MaterialUnknown(MaterialError): pass

@dataclass(frozen=True)
class SchemaPolicy:
    version: str
    canonicalizer_digest: str
    semantic_projector_digest: str
    semantic_fields: tuple[str, ...]

@dataclass(frozen=True)
class Material:
    project_scope: str
    material_id: str
    schema_version: str
    semantic_key: str
    canonical_digest: str
    source_digest: str
    payload: Mapping[str, Any]

def semantic_key(payload: Mapping[str, Any], policy: SchemaPolicy) -> str:
    missing=[k for k in policy.semantic_fields if k not in payload]
    if missing: raise MaterialError(f"missing semantic fields: {missing}")
    projection={k:payload[k] for k in policy.semantic_fields}
    return sha256_hex(canonical_json_bytes(projection))

def build_material(*, project_scope:str, material_id:str, schema_version:str,
                   payload:Mapping[str,Any], source_digest:str,
                   policies:Mapping[str,SchemaPolicy]) -> Material:
    policy=policies.get(schema_version)
    if policy is None: raise MaterialUnknown("unknown material schema version")
    canonical=canonical_json_bytes(dict(payload))
    return Material(project_scope,material_id,schema_version,
                    semantic_key(payload,policy),sha256_hex(canonical),
                    source_digest,dict(payload))

def import_disposition(existing: Material|None, candidate: Material) -> str:
    if existing is None: return "CREATE"
    if (existing.semantic_key==candidate.semantic_key and
        existing.canonical_digest==candidate.canonical_digest and
        existing.source_digest==candidate.source_digest):
        return "VERIFIED"
    raise MaterialConflict("same source/semantic identity has divergent immutable bytes")

def resolve_current_profile(profiles: Sequence[Mapping[str,Any]], project_scope:str) -> Mapping[str,Any]:
    scoped=[p for p in profiles if p.get("project_scope")==project_scope and p.get("accepted") is True]
    if not scoped: raise MaterialUnknown("no accepted profile")
    by_digest={p["profile_digest"]:p for p in scoped}
    genesis=[p for p in scoped if p.get("predecessor_digest") is None]
    if len(genesis)!=1: raise MaterialUnknown("profile genesis is not unique")
    children={}
    for p in scoped:
        pred=p.get("predecessor_digest")
        if pred is not None:
            if pred==p["profile_digest"] or pred not in by_digest: raise MaterialUnknown("invalid predecessor")
            children.setdefault(pred,[]).append(p["profile_digest"])
    if any(len(v)>1 for v in children.values()): raise MaterialUnknown("profile fork")
    seen=set(); cur=genesis[0]
    while True:
        d=cur["profile_digest"]
        if d in seen: raise MaterialUnknown("profile cycle")
        seen.add(d)
        nxt=children.get(d,[])
        if not nxt: break
        cur=by_digest[nxt[0]]
    if len(seen)!=len(scoped): raise MaterialUnknown("disconnected profile chain")
    return cur

def visible_set_digest(materials: Sequence[Material]) -> tuple[str,int]:
    rows=sorted((m.material_id,m.canonical_digest,m.semantic_key) for m in materials)
    return sha256_hex(canonical_json_bytes(rows)),len(rows)
