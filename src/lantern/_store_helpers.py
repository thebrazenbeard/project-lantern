from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from collections.abc import Iterable

from .contracts import RecordEnvelope
from ._store_types import ValidationError


class Transaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> None:
        self.connection.execute("begin immediate")

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if exc_type is None:
            self.connection.execute("commit")
        else:
            self.connection.execute("rollback")
        return False


def _counts(values: Iterable[str]) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)
    for value in values:
        result[value] += 1
    return dict(result)


def _record_dependencies(record: RecordEnvelope) -> set[str]:
    dependencies: set[str] = set()
    if record.predecessor_record_id:
        dependencies.add(record.predecessor_record_id)
    payload = record.payload
    if record.record_type == "Link":
        dependencies.update(
            value for value in (payload.get("source_record_id"), payload.get("target_record_id"))
            if isinstance(value, str)
        )
    elif record.record_type == "StateEvent":
        subject = payload.get("subject_record_id")
        if isinstance(subject, str):
            dependencies.add(subject)
    elif record.record_type == "Assessment":
        claim = payload.get("claim_id")
        if isinstance(claim, str):
            dependencies.add(claim)
    elif record.record_type == "Decision":
        evidence = payload.get("evidence", [])
        if isinstance(evidence, list):
            dependencies.update(item for item in evidence if isinstance(item, str))
    return dependencies


def _dependency_closure(records: dict[str, RecordEnvelope], conflict_ids: set[str]) -> set[str]:
    skipped: set[str] = set()
    changed = True
    while changed:
        changed = False
        unavailable = conflict_ids | skipped
        for record_id, record in records.items():
            if record_id in unavailable:
                continue
            if _record_dependencies(record) & unavailable:
                skipped.add(record_id)
                changed = True
    return skipped


def _topological_records(records: list[RecordEnvelope]) -> list[RecordEnvelope]:
    by_id = {record.record_id: record for record in records}
    indegree = {record.record_id: 0 for record in records}
    children: dict[str, list[str]] = defaultdict(list)
    for record in records:
        for dependency in _record_dependencies(record):
            if dependency in by_id:
                indegree[record.record_id] += 1
                children[dependency].append(record.record_id)
    queue = deque(sorted(record_id for record_id, degree in indegree.items() if degree == 0))
    ordered: list[RecordEnvelope] = []
    while queue:
        record_id = queue.popleft()
        ordered.append(by_id[record_id])
        for child in sorted(children.get(record_id, [])):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(records):
        raise ValidationError("Import records contain a dependency cycle")
    return ordered
