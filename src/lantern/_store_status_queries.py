from __future__ import annotations

import json
from typing import Any

from .contracts import RecordEnvelope


class StatusQueriesMixin:
    def current_assessment(self, *, claim_id: str, assessor_id: str, scope_id: str) -> RecordEnvelope | None:
        lineage_key = f"{claim_id}|{assessor_id}|{scope_id}"
        row = self._connection.execute(
            """
            select r.* from lineage_heads h
            join records r on r.record_id=h.record_id
            where h.project_id=? and h.record_type='Assessment' and h.lineage_key=?
            """,
            (self.project_id, lineage_key),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def review_required(self, subject_record_id: str) -> bool:
        row = self._connection.execute(
            """
            select e.event_type from state_heads h
            join state_events e on e.record_id=h.event_record_id
            where h.subject_record_id=?
            """,
            (subject_record_id,),
        ).fetchone()
        return row is not None and row["event_type"] == "REVIEW_REQUIRED"

    def status(self) -> dict[str, Any]:
        counts = {
            row["record_type"]: row["count"]
            for row in self._connection.execute(
                "select record_type, count(*) as count from records group by record_type order by record_type"
            ).fetchall()
        }
        assessments = []
        for row in self._connection.execute(
            """
            select r.record_id, r.payload_json from lineage_heads h
            join records r on r.record_id=h.record_id
            where r.record_type='Assessment'
            order by r.record_id
            """
        ).fetchall():
            payload = json.loads(row["payload_json"])
            assessments.append({"record_id": row["record_id"], **payload})
        review_rows = self._connection.execute(
            """
            select h.subject_record_id, e.record_id as event_record_id, e.details_json
            from state_heads h join state_events e on e.record_id=h.event_record_id
            where e.event_type='REVIEW_REQUIRED'
            order by h.subject_record_id
            """
        ).fetchall()
        return {
            "schema": "LANTERN_STATUS_V1",
            "project_id": self.project_id,
            "record_counts": counts,
            "current_assessments": assessments,
            "review_required": [
                {
                    "subject_record_id": row["subject_record_id"],
                    "event_record_id": row["event_record_id"],
                    "details": json.loads(row["details_json"]),
                }
                for row in review_rows
            ],
        }
