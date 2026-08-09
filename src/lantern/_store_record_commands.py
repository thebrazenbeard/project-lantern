from __future__ import annotations

from .contracts import build_record
from ._store_types import OperationResult


class RecordCommandsMixin:
    def add_claim(self, *, actor_id: str, claim_key: str, text: str, epistemic_class: str,
                  attributable_to: str, predecessor_record_id: str | None = None,
                  record_id: str | None = None, created_at: str | None = None) -> OperationResult:
        return self.insert_record(build_record(
            project_id=self.project_id, record_type="Claim", actor_id=actor_id,
            record_id=record_id, created_at=created_at,
            provenance={"attributable_to": attributable_to}, lineage_key=claim_key,
            predecessor_record_id=predecessor_record_id,
            payload={"claim_key": claim_key, "text": text, "epistemic_class": epistemic_class,
                     "attributable_to": attributable_to},
        ))

    def add_assessment(self, *, actor_id: str, claim_id: str, assessor_id: str, scope_id: str,
                       disposition: str, rationale: str, predecessor_record_id: str | None = None,
                       record_id: str | None = None, created_at: str | None = None) -> OperationResult:
        lineage_key = f"{claim_id}|{assessor_id}|{scope_id}"
        return self.insert_record(build_record(
            project_id=self.project_id, record_type="Assessment", actor_id=actor_id,
            record_id=record_id, created_at=created_at,
            provenance={"assessor_id": assessor_id, "scope_id": scope_id},
            lineage_key=lineage_key, predecessor_record_id=predecessor_record_id,
            payload={"claim_id": claim_id, "assessor_id": assessor_id, "scope_id": scope_id,
                     "disposition": disposition, "rationale": rationale},
        ))

    def add_decision(self, *, actor_id: str, decision_key: str, authority: str, conclusion: str,
                     evidence: list[str], assumptions: list[str], alternatives: list[str],
                     predecessor_record_id: str | None = None, record_id: str | None = None,
                     created_at: str | None = None) -> OperationResult:
        return self.insert_record(build_record(
            project_id=self.project_id, record_type="Decision", actor_id=actor_id,
            record_id=record_id, created_at=created_at, provenance={"authority": authority},
            lineage_key=decision_key, predecessor_record_id=predecessor_record_id,
            payload={"decision_key": decision_key, "authority": authority, "conclusion": conclusion,
                     "evidence": evidence, "assumptions": assumptions, "alternatives": alternatives},
        ))

    def add_link(self, *, actor_id: str, link_type: str, source_record_id: str,
                 target_record_id: str, record_id: str | None = None,
                 created_at: str | None = None) -> OperationResult:
        if link_type == "CONTRADICTS":
            source_record_id, target_record_id = sorted((source_record_id, target_record_id))
        return self.insert_record(build_record(
            project_id=self.project_id, record_type="Link", actor_id=actor_id,
            record_id=record_id, created_at=created_at,
            provenance={"relationship_author": actor_id},
            payload={"link_type": link_type, "source_record_id": source_record_id,
                     "target_record_id": target_record_id},
        ))
