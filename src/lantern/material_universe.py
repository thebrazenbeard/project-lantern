from __future__ import annotations
from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence
from .canonical import canonical_json_bytes, sha256_hex, strict_json_loads

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

@dataclass(frozen=True)
class SeedImportReceipt:
    source_collective_id: str
    source_event_id: str
    source_reducer_digest: str
    semantic_role: str
    imported_material_digest: str
    material_id: str


def parse_material_json(payload_text: str | bytes) -> Mapping[str, Any]:
    value = strict_json_loads(payload_text)
    if not isinstance(value, dict):
        raise MaterialError("material payload must be a JSON object")
    return value


def semantic_key(payload: Mapping[str, Any], policy: SchemaPolicy) -> str:
    missing=[k for k in policy.semantic_fields if k not in payload]
    if missing: raise MaterialError(f"missing semantic fields: {missing}")
    projection={k:payload[k] for k in policy.semantic_fields}
    return sha256_hex(canonical_json_bytes(projection))


def build_material(*, project_scope:str, material_id:str, schema_version:str,
                   payload:Mapping[str,Any] | None=None, payload_text:str|bytes|None=None,
                   source_digest:str, policies:Mapping[str,SchemaPolicy]) -> Material:
    policy=policies.get(schema_version)
    if policy is None: raise MaterialUnknown("unknown material schema version")
    if (payload is None)==(payload_text is None):
        raise MaterialError("provide exactly one of payload or payload_text")
    value=dict(payload) if payload is not None else dict(parse_material_json(payload_text))
    canonical=canonical_json_bytes(value)
    return Material(project_scope,material_id,schema_version,
                    semantic_key(value,policy),sha256_hex(canonical),source_digest,value)


def import_disposition(existing: Material|None, candidate: Material) -> str:
    if existing is None: return "CREATE"
    immutable=(existing.project_scope,existing.material_id,existing.schema_version,
               existing.semantic_key,existing.canonical_digest,existing.source_digest)
    proposed=(candidate.project_scope,candidate.material_id,candidate.schema_version,
              candidate.semantic_key,candidate.canonical_digest,candidate.source_digest)
    if immutable==proposed: return "VERIFIED"
    raise MaterialConflict("same import/material identity has divergent immutable bytes")


def seed_import_disposition(existing: SeedImportReceipt|None, candidate: SeedImportReceipt) -> str:
    if existing is None: return "CREATE"
    if existing==candidate: return "VERIFIED"
    if (existing.source_collective_id,existing.source_event_id)==(candidate.source_collective_id,candidate.source_event_id):
        raise MaterialConflict("legacy source key reused with divergent import evidence")
    raise MaterialConflict("seed import identity mismatch")


def resolve_current_profile(profiles: Sequence[Mapping[str,Any]], project_scope:str) -> Mapping[str,Any]:
    scoped=[p for p in profiles if p.get("project_scope")==project_scope and p.get("accepted") is True]
    if not scoped: raise MaterialUnknown("no accepted profile")
    by_digest={p["profile_digest"]:p for p in scoped}
    if len(by_digest)!=len(scoped): raise MaterialUnknown("duplicate profile digest")
    genesis=[p for p in scoped if p.get("predecessor_digest") is None]
    if len(genesis)!=1: raise MaterialUnknown("profile genesis is not unique")
    children:dict[str,list[str]]={}
    for p in scoped:
        pred=p.get("predecessor_digest")
        if pred is not None:
            if pred==p["profile_digest"] or pred not in by_digest: raise MaterialUnknown("invalid predecessor")
            children.setdefault(pred,[]).append(p["profile_digest"])
    if any(len(v)>1 for v in children.values()): raise MaterialUnknown("profile fork")
    seen=set(); cur=genesis[0]
    while True:
        digest=cur["profile_digest"]
        if digest in seen: raise MaterialUnknown("profile cycle")
        seen.add(digest)
        nxt=children.get(digest,[])
        if not nxt: break
        cur=by_digest[nxt[0]]
    if len(seen)!=len(scoped): raise MaterialUnknown("disconnected profile chain")
    return cur


def _lp(value:str)->bytes:
    raw=value.encode("utf-8")
    return str(len(raw)).encode("ascii")+b":"+raw


def material_member_bytes(material:Material)->bytes:
    return b"".join(_lp(v) for v in (
        material.material_id,material.canonical_digest,material.semantic_key,material.source_digest
    ))


def visible_set_digest(materials: Sequence[Material]) -> tuple[str,int]:
    ordered=sorted(materials,key=lambda m:m.material_id.encode("utf-8"))
    payload=b"".join(_lp(material_member_bytes(m).decode("utf-8")) for m in ordered)
    return sha256_hex(payload),len(ordered)
