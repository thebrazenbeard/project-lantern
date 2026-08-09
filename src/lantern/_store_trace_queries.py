from __future__ import annotations

import json
from typing import Any

from ._store_types import ValidationError


class TraceQueriesMixin:
    def decision_trace(self, decision_id: str) -> dict[str, Any]:
        decision = self.get_record(decision_id)
        if decision.record_type != "Decision":
            raise ValidationError("decision trace requires a Decision record")
        links = self._connection.execute(
            """
            select l.record_id, l.link_type, l.target_record_id, r.record_type, r.payload_json
            from links l join records r on r.record_id=l.target_record_id
            where l.source_record_id=? order by l.link_type, l.target_record_id
            """,
            (decision_id,),
        ).fetchall()
        dependencies: list[dict[str, Any]] = []
        for row in links:
            target_payload = json.loads(row["payload_json"])
            item: dict[str, Any] = {
                "link_id": row["record_id"],
                "link_type": row["link_type"],
                "target_record_id": row["target_record_id"],
                "target_type": row["record_type"],
                "target_payload": target_payload,
            }
            if row["record_type"] == "Claim":
                evidence_rows = self._connection.execute(
                    """
                    select l.record_id, l.link_type, l.source_record_id, r.payload_json
                    from links l join records r on r.record_id=l.source_record_id
                    where l.target_record_id=? and l.link_type in ('SUPPORTS','OPPOSES')
                    order by l.link_type, l.source_record_id
                    """,
                    (row["target_record_id"],),
                ).fetchall()
                contradiction_rows = self._connection.execute(
                    """
                    select l.record_id, l.source_record_id, l.target_record_id
                    from links l
                    where l.link_type='CONTRADICTS'
                      and (l.source_record_id=? or l.target_record_id=?)
                    order by l.record_id
                    """,
                    (row["target_record_id"], row["target_record_id"]),
                ).fetchall()
                item["claim_evidence"] = [
                    {
                        "link_id": ev["record_id"],
                        "link_type": ev["link_type"],
                        "source_record_id": ev["source_record_id"],
                        "source_payload": json.loads(ev["payload_json"]),
                    }
                    for ev in evidence_rows
                ]
                item["contradictions"] = [dict(contradiction) for contradiction in contradiction_rows]
            dependencies.append(item)
        return {
            "schema": "LANTERN_DECISION_TRACE_V1",
            "decision": decision.to_dict(),
            "dependencies": dependencies,
            "review_required": self.review_required(decision_id),
        }
