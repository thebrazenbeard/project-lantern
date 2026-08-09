from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Any

from .canonical import canonical_json
from .contracts import RecordEnvelope, build_record
from ._store_types import ConflictError, ValidationError

_LINK_MATRIX: dict[str, tuple[set[str], set[str]]] = {
    "SUPPORTS": ({"SourceSnapshot"}, {"Claim"}),
    "OPPOSES": ({"SourceSnapshot"}, {"Claim"}),
    "CONTRADICTS": ({"Claim"}, {"Claim"}),
    "DEPENDS_ON": ({"Assessment", "Decision"}, {"SourceSnapshot", "Claim"}),
}


class ProjectionMixin:
    def _record_type(self, record_id: str) -> str:
        row = self._connection.execute("select record_type from records where record_id=?", (record_id,)).fetchone()
        if row is None:
            raise ValidationError(f"Unknown link endpoint: {record_id}")
        return str(row["record_type"])

    def _project_link(self, record: RecordEnvelope) -> None:
        payload = record.payload
        link_type = payload["link_type"]
        source = payload["source_record_id"]
        target = payload["target_record_id"]
        source_type = self._record_type(source)
        target_type = self._record_type(target)
        allowed_sources, allowed_targets = _LINK_MATRIX[link_type]
        if source_type not in allowed_sources or target_type not in allowed_targets:
            raise ValidationError(f"Invalid endpoint matrix for {link_type}: {source_type} -> {target_type}")
        try:
            self._connection.execute(
                "insert into links(record_id,link_type,source_record_id,target_record_id) values (?,?,?,?)",
                (record.record_id, link_type, source, target),
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Duplicate semantic Link") from exc

    def _project_state_event(self, record: RecordEnvelope) -> None:
        payload = record.payload
        subject = payload["subject_record_id"]
        event_type = payload["event_type"]
        event_key = payload["event_key"]
        current = self._connection.execute(
            "select event_record_id from state_heads where subject_record_id=?", (subject,)
        ).fetchone()
        expected = current["event_record_id"] if current is not None else None
        if record.predecessor_record_id != expected:
            raise ConflictError("Stale StateEvent predecessor")
        self._connection.execute(
            """insert into state_events(record_id,subject_record_id,event_type,predecessor_event_id,event_key,details_json)
            values (?,?,?,?,?,?)""",
            (record.record_id, subject, event_type, record.predecessor_record_id, event_key,
             canonical_json(payload.get("details", {}))),
        )
        self._connection.execute(
            """insert into state_heads(subject_record_id,event_record_id) values (?,?)
            on conflict(subject_record_id) do update set event_record_id=excluded.event_record_id""",
            (subject, record.record_id),
        )

    def _emit_state_event(self, *, subject_record_id: str, event_type: str, event_key: str,
                          details: dict[str, Any], actor_id: str = "lantern-system") -> str:
        existing = self._connection.execute(
            "select record_id from state_events where event_key=?", (event_key,)
        ).fetchone()
        if existing is not None:
            return str(existing["record_id"])
        head = self._connection.execute(
            "select event_record_id from state_heads where subject_record_id=?", (subject_record_id,)
        ).fetchone()
        predecessor = str(head["event_record_id"]) if head is not None else None
        event = build_record(
            project_id=self.project_id, record_type="StateEvent", actor_id=actor_id,
            created_at=datetime.now(UTC),
            provenance={"generated_by": "LanternStore", "authority": "DERIVED_OPERATIONAL_EVENT"},
            lineage_key=f"state:{subject_record_id}", predecessor_record_id=predecessor,
            payload={"subject_record_id": subject_record_id, "event_type": event_type,
                     "event_key": event_key, "details": details},
        )
        self._insert_record_row(event)
        self._project_state_event(event)
        return event.record_id

    def _emit_supersession_effects(self, successor: RecordEnvelope) -> None:
        predecessor = successor.predecessor_record_id
        if predecessor is None:
            return
        self._emit_state_event(
            subject_record_id=predecessor, event_type="SUPERSEDED",
            event_key=f"superseded:{predecessor}:{successor.record_id}",
            details={"predecessor_record_id": predecessor, "successor_record_id": successor.record_id},
        )
        dependents = self._connection.execute(
            """select l.record_id as link_id,l.source_record_id as dependent_id,
            r.record_type,r.project_id,r.lineage_key from links l join records r on r.record_id=l.source_record_id
            where l.link_type='DEPENDS_ON' and l.target_record_id=?
            and r.record_type in ('Assessment','Decision') order by l.source_record_id,l.record_id""",
            (predecessor,),
        ).fetchall()
        for row in dependents:
            if row["lineage_key"] is not None:
                current = self._connection.execute(
                    "select record_id from lineage_heads where project_id=? and record_type=? and lineage_key=?",
                    (row["project_id"], row["record_type"], row["lineage_key"]),
                ).fetchone()
                if current is None or current["record_id"] != row["dependent_id"]:
                    continue
            self._emit_state_event(
                subject_record_id=str(row["dependent_id"]), event_type="REVIEW_REQUIRED",
                event_key=f"review-required:{row['dependent_id']}:{predecessor}:{successor.record_id}:{row['link_id']}",
                details={"predecessor_record_id": predecessor, "successor_record_id": successor.record_id,
                         "dependency_link_id": row["link_id"], "trigger": "DIRECT_DEPENDS_ON_SUPERSESSION"},
            )
